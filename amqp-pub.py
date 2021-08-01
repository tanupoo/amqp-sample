#!/usr/bin/env python

import pika
import sys
import time
from util import amqp_prepare, parse_args, print_opts

def main():
    opt = parse_args(sys.argv[1:], consumer=False)
    channel = amqp_prepare(opt)

    # create a message.
    if opt.message == "-":
        # take a message from stdin.
        opt.message = sys.stdin.read()
    if opt.message_size is not None:
        # adjust the message according to the message_size
        opt.message = (opt.message +
                    "".join([str(i%10) for i in range(opt.message_size)])
                    )[:opt.message_size]
    else:
        # set message_size if not specified.
        # it allows to send a 0 size message.
        opt.message_size = len(opt.message)

    def make_message(opt, nb_count):
        """
        if opt.nb_messages is 1, return message as it is.
        otherwise, add the number of count into the message.
        """
        if opt.nb_messages == 1:
            return opt.message
        else:
            if opt.pub_name:
                message = f"{opt.pub_name}:{nb_count}:{opt.message}"
            else:
                message = f"{nb_count}:{opt.message}"
            return message.ljust(opt.message_size)

    print_opts(opt, consumer=False)

    # publishing
    # https://pika.readthedocs.io/en/stable/modules/adapters/blocking.html?highlight=queue_declare#pika.adapters.blocking_connection.BlockingChannel.basic_publish
    def on_return_callback(channel, method, properties, body):
        print("==> return_callback", channel, method, properties, body)

    def on_cancel_callback(channel, method, properties, body):
        print("==> cancel_callback", channel, method, properties, body)

    def on_close_callback(channel, method, properties, body):
        print("==> close_callback", channel, method, properties, body)

    channel.add_on_return_callback(on_return_callback)
    channel.add_on_cancel_callback(on_cancel_callback)
    # BlockingChannel' object has no attribute 'add_on_close_callback
    #channel.add_on_close_callback(on_close_callback)

    if opt.confirm:
        channel.confirm_delivery()

    properties = pika.BasicProperties(
        delivery_mode=2 if opt.persistent == True else 1,
        priority=opt.priority,      # str, not int
        expiration=opt.message_ttl,    # str, not int
    )

    nb_count = 0
    while True:
        nb_count += 1
        message = make_message(opt, nb_count)
        try:
            channel.basic_publish(
                    exchange=opt.exchange_name,
                    routing_key=opt.routing_key,
                    body=message,
                    properties=properties,
                    mandatory=opt.mandatory)
        except pika.exceptions.ChannelClosedByBroker as e:
            print("ERROR: ", e)
        except pika.exceptions.UnroutableError as e:
            print("ERROR: ", e)
        else:
            print(f"Sent: {message}")
        # check to send next message
        if opt.nb_messages == nb_count:
            break
        else:
            time.sleep(opt.publish_interval)
        # to next message.

    channel.connection.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        print("Stopped")
