import pika
import ssl

def amqp_prepare(opt):
    kwargs = {
            "host": opt.server_name,
            "port": opt.port_number,
            }
    if opt.vhost is not None:
        kwargs.update(dict(virtual_host=opt.vhost))
    # TLS options
    if opt.cafile or opt.subjectname:
        opt.enable_tls = True
    if opt.enable_tls is True:
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        if opt.subjectname is None:
            opt.subjectname = opt.server_name
        if opt.cafile is not None:
            context.load_verify_locations(cafile=opt.cafile)
        else:
            # allow any certificates and a subject name.
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        kwargs.update(dict(ssl_options=pika.SSLOptions(context,
                                                       opt.subjectname)))
    # creadentials
    if opt.userpass is not None:
        u, p = opt.userpass.split(":")
        kwargs.update(dict(credentials=pika.credentials.PlainCredentials(u, p)))
        if opt.enable_tls is False:
            print("WARNING: the connection is not secured.")
    # connection params
    params = pika.ConnectionParameters(**kwargs)
    # create the connection.
    try:
        connection = pika.BlockingConnection(params)
    except pika.exceptions.ProbableAccessDeniedError as e:
        print(e)
        exit(-1)
    except pika.exceptions.ProbableAuthenticationError as e:
        print(e)
        exit(-1)

    channel = connection.channel()

    if opt.create_exchange:
        result = channel.exchange_declare(
                exchange=opt.exchange_name,
                exchange_type=opt.exchange_type,
                durable=opt.durable_exchange,
                auto_delete=opt.auto_delete_exchange,
                )
        print(f"Created exchange: {opt.exchange_name}")

    arguments = {}
    if opt.queue_ttl is not None:
        arguments.update({"x-expires": int(opt.queue_ttl)})   # int, not str
    if opt.message_ttl is not None:
        arguments.update({"x-message-ttl": opt.message_ttl}) # str, not int

    if opt.create_queue:
        try:
            result = channel.queue_declare(
                        queue=opt.queue_name,
                        durable=opt.durable_queue,
                        auto_delete=opt.auto_delete_queue,
                        arguments=arguments
                        )
        except pika.exceptions.ChannelClosedByBroker as e:
            print(e)
            exit(-1)
        opt.queue_name = result.method.queue
        print(f"Created queue: {opt.queue_name}")

    if opt.bind_queue:
        channel.queue_bind(
                exchange=opt.exchange_name,
                queue=opt.queue_name,
                routing_key=opt.routing_key)
        print(f"Bound Queue [{opt.queue_name}] to Exchange [{opt.exchange_name}] {opt.routing_key}")

    return channel

#
# argument parser
#
from argparse import ArgumentParser

def parse_args(args, consumer=True):
    ap = ArgumentParser(description="Publisher of AMQP Exchange Topic.")
    # exchange
    ap.add_argument("-e", action="store", dest="exchange_name",
                    default="",
                    help="specify a exchange name.")
    ap.add_argument("-t", action="store", dest="exchange_type",
                    default="direct",
                    help="specify a exchange type.")
    ap.add_argument("-E", "--create-exchange",
                    action="store_true", dest="create_exchange",
                    help="specify to create an exchange.")
    ap.add_argument("--durable-exchange", action="store_true",
                    dest="durable_exchange",
                    help="make the exchange durable.")
    ap.add_argument("--nad-exchange", action="store_false",
                    dest="auto_delete_exchange",
                    help="negate auto-delete for the exchange.")
    # queue
    ap.add_argument("-q", action="store", dest="queue_name",
                    default="",
                    help="specify a server name.")
    ap.add_argument("-Q", "--create-queue",
                    action="store_true", dest="create_queue",
                    help="specify to create a queue.")
    ap.add_argument("--bind-queue", action="store_true", dest="bind_queue",
                    help="specify to bind a queue to the exchangge.")
    ap.add_argument("--durable-queue", action="store_true",
                    dest="durable_queue",
                    help="make the queue durable.")
    ap.add_argument("--exclusive", action="store_true", dest="exclusive_queue",
                    help="make the queue exclusive.")
    ap.add_argument("--nad-queue", action="store_false",
                    dest="auto_delete_queue",
                    help="negate auto-delete for the queue.")
    ap.add_argument("--queue-ttl", action="store", dest="queue_ttl",
                    help="specify the queue's TTL in milliseconds.")
    ap.add_argument("--ack-auto", action="store_true", dest="ack_auto",
                    help="specify to use the automatic acknowledgement.")
    if consumer is True:
        ap.add_argument("--prefetch", action="store", dest="prefetch_count",
                        type=int,
                        help="specify a prefetch count.")
    # publisher / consumer
    ap.add_argument("-k", "--routing-key", action="store", dest="routing_key",
                    default="",
                    help="specify a routing key.")
    ap.add_argument("--mandatory", action="store_true", dest="mandatory",
                    help="let the server return the unroutable message "
                        "when the one was not able to be queued.")
    ap.add_argument("--persistent", action="store_true", dest="persistent",
                    help="make the message persistent.")
    # for consumer, need message_ttl in queue ?
    ap.add_argument("--message-ttl", action="store", dest="message_ttl",
                    help="specify the message's TTL in milliseconds.")
    if consumer is False:
        ap.add_argument("-m", "--message", action="store", dest="message",
                        default="",
                        help="specify a message. "
                            "taken it from stdin if '-' is specified.")
        ap.add_argument("--message-size", action="store", dest="message_size",
                        type=int,
                        help="specify a message size.")
        ap.add_argument("--nb-messages", action="store", dest="nb_messages",
                        type=int, default=1,
                        help="specify the number of messages to be sent. "
                            "0 means infinite. ")
        ap.add_argument("--interval", action="store", dest="publish_interval",
                        type=float, default=1.0,
                        help="specify the interval in seconds "
                            "to send a next message. ")
        ap.add_argument("--pub-name", action="store", dest="pub_name",
                        help="specify a name of this publisher "
                            "that is put into the message, "
                            "is useful for consumer to identify a publisher.")
        ap.add_argument("--priority", action="store", dest="priority",
                        help="specify the priority of the message.")
        ap.add_argument("--confirm", action="store_true", dest="confirm",
                        help="specify to use the confirm mode.")
    if consumer is True:
        ap.add_argument("--lazy", action="store", dest="exit_timer",
                        type=float,
                        help="specify the number of timer to exit "
                            "immediately after it gets a message.")
    # common
    ap.add_argument("--server-name", action="store", dest="server_name",
                    default="localhost",
                    help="specify AMQP server name.")
    ap.add_argument("--port-number", action="store", dest="port_number",
                    type=int, default=5672,
                    help="specify AMQP port number.")
    ap.add_argument("--vhost", action="store", dest="vhost",
                    help="specify vhost.")
    ap.add_argument("--userpass", action="store", dest="userpass",
                    help="specify username and password separated by ':'.")
    ap.add_argument("--enable-tls", action="store_true", dest="enable_tls",
                    help="enable TLS.")
    ap.add_argument("--cafile", action="store", dest="cafile",
                    help="specify CA file. "
                        "It implicitly enables TLS.")
    ap.add_argument("--subjectname", action="store", dest="subjectname",
                    help="specify the server's name in the certficate. "
                        "It implicitly enables TLS.")
    ap.add_argument("--verbose", action="store_true", dest="verbose",
                    help="enable verbose mode.")
    return ap.parse_args(args)

def print_opts(opt, consumer=True):
    if opt.verbose:
        # Exchange
        print("Exchange")
        print("  Name:", opt.exchange_name,
            "C" if opt.create_exchange else "")
        print("  Type:", opt.exchange_type)
        print("  Durable:", opt.durable_exchange)
        print("  Auto Delete:", opt.auto_delete_exchange)
        # Queue
        print("Queue")
        print("  Confirm:", opt.confirm)
        print("  Name:", opt.queue_name,
            "C" if opt.create_queue else "",
            "B" if opt.bind_queue else "")
        print("  Durable:", opt.durable_queue)
        print("  Exclusive:", opt.exclusive_queue)
        print("  Auto Delete:", opt.auto_delete_queue)
        print("  TTL:", opt.queue_ttl)
        print("  ACK type:", "auto" if opt.ack_auto else "basic")
        if consumer is True:
            print("  Prefetch:", opt.prefetch_count)
        """
        queues are supposed to be used for client-specific or connection
        (session)-specific data.
        """
        # Message
        print("Message:")
        print("  Routing Key:", opt.routing_key)
        print("  Mandatory:", opt.mandatory)
        print("  Persistent:", opt.persistent)
        if consumer is False:
            print("  TTL:", opt.message_ttl)
            print("  Priority:", opt.priority)
            print("  Message(max.):", opt.message)
            print("  Length:", opt.message_size)

