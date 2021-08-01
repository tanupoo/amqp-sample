#!/usr/bin/env python

import pika
import sys
import time
from util import amqp_prepare, parse_args, print_opts

def main():

    opt = parse_args(sys.argv[1:])
    channel = amqp_prepare(opt)
    print_opts(opt, consumer=True)

    def on_message_callback(ch, method, properties, body):
        print(f"Received: {body.decode()}")
        if opt.verbose:
            print(f"  Channel: {ch}")
            print(f"  Method: {method}")
            print(f"  Props: {properties}")
        if opt.exit_timer is not None:
            time.sleep(opt.exit_timer)
            exit(0)
        if not opt.ack_auto:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    if opt.prefetch_count is not None:
        channel.basic_qos(prefetch_count=opt.prefetch_count)

    try:
        channel.basic_consume(
                queue=opt.queue_name,
                on_message_callback=on_message_callback,
                auto_ack=True if opt.ack_auto else False)
    except pika.exceptions.ChannelClosedByBroker as e:
        print(e)
        exit(0)

    channel.start_consuming()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        print("Stopped")
