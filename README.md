AMQP(RabbitMQ)ノードのサンプルコード
====================================

Brocking Channelで作ってみた。

[Tutorials](://www.rabbitmq.com/getstarted.html)と同じ動作をさせるための考察。

Hello Worldの最初の例以外は、最初にConsumerがキューを作り、
Publisherからのメッセージを待つようにした。

## [Hello World!](https://www.rabbitmq.com/tutorials/tutorial-one-python.html)

端末を2つ用意して、それぞれ下記のコマンドを実行する。

Consumer側

```
% amqp-con.py -q hello -Q
```

- `-q hello`: キュー*hello*を指定する。
- `-Q`: キューがなければ作る。

Publisher側

```
% amqp-pub.py -q hello -Q -k hello -m 'Hello World!'
```

- `-q hello`: キュー*hello*を指定する。
- `-Q`: キューがなければ作る。
- `-k hello`: routing keyを指定する。

Exchangeタイプを指定しないと名無しのDirect exchangeになる。
Direct exchangeでは、Publisher側はrouging keyを使ってキュー*hello*に
配送することをBrokerに伝える。

チュートリアルではack modeはautoになっているが、
動作の表面上の挙動には影響がないのでautoを指定していない。

また、Consumer,Publisher両方でdeclare_queue()を呼んでいる。
つまり、最初に呼んだ方がキューを作っている。
これを最初にConsumerがキュー*hello*を作り、
Publisherからのメッセージを待つようにしてみる。

Consumer側

```
% amqp-con.py -q hello -Q
```

Publisher側

```
% amqp-pub.py -k hello --mandatory --confirm -m 'Hello World!'
```

- Consumer側でキューを作ることが分かっていれば、`-q hello -Q`は必要ない。
- `--mandatory`: キューに配送できないとエラーが返るようにする。
- `--confirm`: baskc.ackまたはbasic.nackを受信したかチェックする。
    + https://www.rabbitmq.com/confirms.html#publisher-confirms
- amqp-con.pyのack modeの初期値はbasicになっている。
- あえてack-modeをautoにするには`--ack-auto`をつける。
- autoとbasicの挙動の違いは次のwork queueを参照のこと。

## TLSを使ってHello Worldを実行してみる。

- 前準備
    + virtual hostとして domain1を作る。
    + ユーザaliceとbobを作る。

```
rabbitmqctl add_vhost domain1

rabbitmqctl add_user alice alice123
rabbitmqctl set_permissions --vhost domain1 alice123 '.*' '.*' '.*'

rabbitmqctl add_user bob bob123
rabbitmqctl set_permissions --vhost domain1 bob '' '' '.*'
```

Publisher側は、ユーザ名/パスワードを使ってログインしてからメッセージを送信する。

```
% amqp-pub.py -q hello -Q -k hello -m 'Hello World!' --userpass alice:alice123 --vhost domain1
WARNING: the connection is not secured.
Created queue: hello
Sent: Hello World!
```

Consumerも同様にログインしてから受信する。

```
% amqp-con.py -q hello --vhost domain1 --userpass bob:bob123   
WARNING: the connection is not secured.
Received: Hello World!
```

TLSを有効にする。証明書の検証はしていない。

```
amqp-pub.py -q hello -Q -k hello -m 'Hello World!' --port-number 5671 --enable-tls --userpass alice:alice123 --vhost domain1
Created queue: hello
Sent: Hello World!
```

Brokerの証明書を検証するためにCAファイルとBrokerのsubjectnameを指定する。

```
amqp-pub.py -q hello -Q -k hello -m 'Hello World!' --port-number 5671 --cafile chain.pem --subjectname sakura.tanu.org --userpass alice:alice123 --vhost domain1
Created queue: hello
Sent: Hello World!
```


## [Work Queues](https://www.rabbitmq.com/tutorials/tutorial-two-python.html)

端末を2つ開いて下記コマンドでConsumerを2つ起動する。

```
amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
```

- `--durable-queue`: サーバが落ちてもキューが消えないようにする。
- `--nad-queue`: Publisher/Consumerが落ちてもキューが消えないようにする。
- `--prefetch 1`: work queueがACKを返すまでは次のメッセージを受け取らないようにする。全てのworkerでこのオプションを指定すると結果的にfair dispatchingになる。

次に、3つ目の端末を開いて、Publisherを起動する。

```
amqp-pub.py -t direct -k task_queue --persistent --nb-messages 4 -m 'Hello!'
```

- `-t direct`: Exchangeタイプをdirectにする。
- `--persistent`: Brokerがメッセージを配送する前にディスクに書き込む。
- `--nb-messages 4`: 4つメッセージをデフォルトの送信間隔1秒で送信する。

下記の様にPublisherは4つのメッセージを送信した。

```
% amqp-pub.py -t direct -k task_queue --persistent --nb-messages 4 -m 'Hello!'
Sent: 1 Hello!
Sent: 2 Hello!
Sent: 3 Hello!
Sent: 4 Hello!
```

これに対して、2つのConsumerに交互にメッセージが渡るのが分かる。

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
Created queue: task_queue
Received: 1 Hello!
Received: 3 Hello!
```

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
Created queue: task_queue
Received: 2 Hello!
Received: 4 Hello!
```

一度止めて、下記のコマンドでConsumer,Consumer,Publisherを起動してみる。
順序に注意。

```
amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1 --lazy 3
amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
amqp-pub.py -t direct -k task_queue --persistent --nb-messages 4 -m 'Hello!'
```

- `--lazy 3`: メッセージを1つ受け取った後、ack.basicを返さずに3秒後にexit()する。Consumerが処理の途中で落ちた事をエミュレートしている。

便宜上、`--lazy 3`がついているConsumerをLAZYと呼ぶ。
もう一つのConsumerをSOBERと呼ぶ。

Publisherは下記の様に4つのメッセージを送信した。

```
% amqp-pub.py -t direct -k task_queue --persistent --nb-messages 4 -m 'Hello!'
Sent: 1:Hello!
Sent: 2:Hello!
Sent: 3:Hello!
Sent: 4:Hello!
```

これに対して、最初に起動したLAZYは、
1番目のメッセージを受信した後にack.basicを返さずにexit()した。

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1 --lazy 3
Created queue: task_queue
Received: 1:Hello!
```

すると、Brokerが1番目のメッセージをrequeueして、
SOBERがそのメッセージを後から受信した事が分かる。

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
Created queue: task_queue
Received: 2:Hello!
Received: 3:Hello!
Received: 4:Hello!
Received: 1:Hello!
```

次に、全て止めて、
下記のコマンドでConsumer(LAZY),Consumer(SOBER),Publisherを起動してみる。
同様に順序に注意。

```
amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1 --lazy 3 --ack-auto
amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
amqp-pub.py -t direct -k task_queue --persistent --nb-messages 4 -m 'Hello!'
```

- `--ack-auto`: Automatic Acknowledgementを指定する。

LAZYでは、同様に1番目のメッセージを受信した後にack.basicを返さずにexit()した。

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1 --lazy 3 --ack-auto
Created queue: task_queue
Received: 1:Hello!
```

SOBERでは、今度は、1番目と3番目のメッセージが消えた事が分かる。

```
% amqp-con.py -q task_queue -Q --durable-queue --nad-queue --prefetch 1
Created queue: task_queue
Received: 2:Hello!
Received: 4:Hello!
```

これは、LAZYがAutomatic Acknowledgementで動作しているため、
Brokerは1番目と3番目のメッセージの配送が暗黙に成功したと判断しているからである。

## [Publish/Subscribe](https://www.rabbitmq.com/tutorials/tutorial-three-python.html)

Pub/Subではコンシューマが複数いる場合もあるので、`--ack-auto`を指定している。
場合によっては、ackが必要な場合もあるので使い分ける。

端末を2つ開いて下記コマンドでConsumerを2つ起動する。

```
amqp-con.py -e logs -E -t fanout -Q --exclusive --bind-queue --ack-auto
```

`-e logs`: Exchangeに名前logsをつける。
`-E`: Exchangeを作る。
`-t fanout`: Exchangeタイプをfanoutにする。
`--exclusive`: 他のノードが使えないようにする。
`--bind-queue`: キューをExchangeに紐付ける。

次に、3つ目の端末を開いて、Publisherを起動する。

```
amqp-pub.py -e logs -t fanout --nb-message 3 -m 'Hello World!'
```

Publisherは、1秒毎に3回メッセージを送信する。

```
% amqp-pub.py -e logs -t fanout --nb-message 3 -m 'Hello World!'
Sent: 1:Hello World!
Sent: 2:Hello World!
Sent: 3:Hello World!
```

Consumerはそれぞれ別のキューを作っている。
Publisherが1つメッセージを出すと、2つのConsumerに送信されているのが分かる。

```
% amqp-con.py -e logs -E -t fanout -Q --exclusive --bind-queue --ack-auto
Created exchange: logs
Created queue: amq.gen-lHUA6ikzU8HFbj1GESHMZg
Bound Queue [amq.gen-lHUA6ikzU8HFbj1GESHMZg] to Exchange [logs] 
Received: 1:Hello World!
Received: 2:Hello World!
Received: 3:Hello World!
```

```
% amqp-con.py -e logs -E -t fanout -Q --exclusive --bind-queue --ack-auto
Created exchange: logs
Created queue: amq.gen-8iNpPPLWOtu3I7GqYAN7Zw
Bound Queue [amq.gen-8iNpPPLWOtu3I7GqYAN7Zw] to Exchange [logs] 
Received: 1:Hello World!
Received: 2:Hello World!
Received: 3:Hello World!
```

例えば、Publisher側でExchange *logs*が存在しない場合に即時エラーにしたい場合は、
`--mandatory --confirm`をつける。

```
% amqp-pub.py -e logs -t fanout -m 'Hello World!' --mandatory --confirm
ERROR:  (404, "NOT_FOUND - no exchange 'logs' in vhost '/'")
```

BlockingConnectionでは、BrokerやConsumerからの通知は次の送信時に分かる。
このオプションがなくても、次の送信時にエラーを検知することができる。

```
% amqp-pub.py -e logs -t fanout -m 'Hello World!' --nb-messages 2
Sent: 1:Hello World!
ERROR:  (404, "NOT_FOUND - no exchange 'logs' in vhost '/'")
```

## [Routing](https://www.rabbitmq.com/tutorials/tutorial-four-python.html)

routing keyで配送するキューを切り替える。

端末を1つ開いて下記コマンドでConsumerを起動する。
routing keyにerrorを指定している。

```
amqp-con.py -e direct_logs -E -t direct -k error -Q --exclusive --bind-queue --ack-auto
```

2つ目の端末を開いて下記コマンドでConsumerを起動する。
こちらはrouting keyにinfoを指定している。

```
amqp-con.py -e direct_logs -E -t direct -k info -Q --exclusive --bind-queue --ack-auto
```

3つ目の端末を開いて下記コマンドでPublisherを起動する。
routing keyをerrorにしてメッセージを送信する。

```
amqp-pub.py -e direct_logs -t direct -m 'Hello World!' -k error
```

routing keyをerrorに指定したConsumerに配送される。

```
% amqp-con.py -e direct_logs -E -t direct -k error -Q --exclusive --bind-queue --ack-auto
Created exchange: direct_logs
Created queue: amq.gen-gWUt8eu40pqog_ZyksHLSQ
Bound Queue [amq.gen-gWUt8eu40pqog_ZyksHLSQ] to Exchange [direct_logs] error
Received: Hello World!
```

次に、Publisherでrouting keyをinfoにしてメッセージを送信する。

```
amqp-pub.py -e direct_logs -t direct -m 'Hello World!' -k info
```

すると、今度はrouging keyをinfoにしたConsumerに配送される。

```
% amqp-con.py -e direct_logs -E -t direct -k info -Q --exclusive --bind-queue --ack-auto
Created exchange: direct_logs
Created queue: amq.gen-5-XV137j1JVt17pbr6xjrw
Bound Queue [amq.gen-5-XV137j1JVt17pbr6xjrw] to Exchange [direct_logs] info
Received: Hello World!
```

## [Topics](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)

Topicを使った配送。

端末を3つ開いて下記コマンドでConsumerを3つ起動する。
routing keyは、それぞれ jp.lg.tokyo, jp.lg.chiba, jp.lg.# にしている。

```
amqp-con.py -e topic_logs -E -t topic -Q --exclusive --bind-queue --ack-auto -k jp.lg.tokyo
amqp-con.py -e topic_logs -E -t topic -Q --exclusive --bind-queue --ack-auto -k jp.lg.chiba
amqp-con.py -e topic_logs -E -t topic -Q --exclusive --bind-queue --ack-auto -k 'jp.lg.#'
```

初期状態だと、アカウントguestのmax-connectionsが3になっているので、
adminで3以上にする。

```
pika.exceptions.ProbableAccessDeniedError: ConnectionClosedByBroker: (530) "NOT_ALLOWED - access to vhost '/' refused for user 'guest': connection limit (3) is reached"
```

Publisherでrouting keyを変えてみると、それに従い配送されるのが分かる。

```
amqp-pub.py -e topic_logs -t topic -k jp.lg.chiba
amqp-pub.py -e topic_logs -t topic -k jp.lg.tokyo
```

