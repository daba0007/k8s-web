## k8s-web集群架构从零开始
k8s作为一个架构，本身搭建环境就是一件十分费事的事情。我尝试了许多种方法，希望能够实现最快最直接搭建，先列举以下我的尝(cai)试(keng)过程

### k8s搭建历程
1. 我尝试使用rancher来搭建。rancher是一个开源的全栈化企业级容器管理平台，它提供了k8s的部署。我们所要做的只需要添加主机进去，然后rancher就会帮助我们部署。然而在本朝（咳咳）这个部署确实有点压力，并不完全因为拉取镜像很慢，所以有条件的人可以试一下，不过我只能尝试别的方法了。

2. 最麻烦的方法当然是直接手工安装了。手工安装不仅能够帮助我们更加了解k8s的流程，也是最能保证每个步骤都是不出错的。但是及其复杂。具体我已经写了一份md文档，有兴趣的同学可以参考一下

3. 第三种方法是我在网上找的，有好心的同学已经把手工安装写为了ansible的playbook，这样安装就很方便了，这里真的要感谢它。

## k8s-web搭建


>以下涉及了很多yaml文件的编写，我基本做注释，不过作过注释的不会重复注释，希望读者能消化完再继续读下去
## redis服务
说了这么多，我们的k8s集群总算搭建起来了。根据我们之前的web集群，我们首先就来搭建一个redis主从配置架构。

### 原理
对于持久型数据库（Mysql、Oracle以及SqlServer）来说，它们将数据存储在我们部署数据库的机器的硬盘中，当网站的处理和访问量非常大的时候，我们的数据库的压力就变大了。想要提高网站的效率，降低数据库的读写次数，我们就需要引入缓存技术。缓存就是在内存中存储的数据备份，当数据没有发生本质改变的时候，我们就不让数据的查询去
数据库进行操作，而去内存中取数据，这样就大大降低了数据库的读写次数，而且从内存中读数据的速度比去数据库查询要快一些，这样同时又提高了效率。

redis做缓存不仅仅支持简单的k/v类型的数据，同时还提供list，set，zset，hash等数据结构的存储，并且支持数据持久化，可以将内存中的数据保持在磁盘中，重启的时候可以再次加载进行使用。和memcache，它单个value的最大限制是1GB，memcached只能保存1MB的数据。

所以，我们的web集群就采用redis作为缓存服务。

### 主从

首先是构建一个我们自己的redis镜像。redis镜像分为两种，一种是redis-master，一种是redis-slave。redis的复制功能是支持多个数据库之间的数据同步，一类是主数据库（master）一类是从数据库（slave），主数据库可以进行读写操作，当发生写操作的时候自动将数据同步到从数据库，而从数据库一般是只读的，并接收主数据库同步过来的数据，一个主数据库可以有多个从数据库，而一个从数据库只能有一个主数据库。

通过redis的复制功能可以很好的实现数据库的读写分离，提高服务器的负载能力。主数据库主要进行写操作，而从数据库负责读操作。

过程：
1. 当一个从数据库启动时，会向主数据库发送sync命令，
2. 主数据库接收到sync命令后会开始在后台保存快照（执行rdb操作），并将保存期间接收到的命令缓存起来
3. 当快照完成后，redis会将快照文件和所有缓存的命令发送给从数据库。
4. 从数据库收到后，会载入快照文件并执行收到的缓存的命令。

### redis-master

我们可以使用docker pull的命令拉取一个标准的redis镜像(上次发现拉取在本朝拉取daocloud.io的镜像炒鸡快)
```
docker pull daocloud.io/redis
```
之后我需要编写自己的redis.conf，并且把它放到镜像中以供使用（主要是注释bind以开启远程访问以及使用后台模式）

我的dockerfile如下
```
FROM daocloud.io/redis

MAINTAINER daba0007

ADD redis-master.conf /etc/redis/redis.conf

WORKDIR /etc/redis/

CMD redis-server redis.conf

```
构造一个dockerfile，并把它push到我的仓库里
```
docker build -t daba0007/redis-master  .
docker push daba0007/redis-master
```
这样就有了我要的redis-master镜像

然后开始使用k8s,首先写一个redis-master-rc.yaml
```yaml
apiVersion: v1                              # api版本
kind: ReplicationController                 # 类型是rc
metadata:                                   # 元数据(就是rc的对象)
  name: redis-master
spec:                                       #
  replicas: 1                               # 表示运行1个pod实例，如果多个pod可做LB和HA
  selector:                                 # 是RC的pod选择器，即监视和管理拥有这些标签的pod实例。当运行的pod实例小于replicas时，RC会根据spec下的template段定义的pod模板来生成一个新的pod实例。
    name: redis-master
  template:                                 # 定义的模板，pod实例不足时会运行
    metadata:
      labels:                              # lables属性指定了该Pod的标签，注意：这里的lables必须匹配RC的 spec:selector
        name: redis-master
    spec:
      containers:
      - name: redis-master
        image: daba0007/redis-master
        ports:
        - containerPort: 6379

```
执行命令，将它发布到k8s集群中
```
[root@k8s-master redis-master]# kubectl create -f redis-master-rc.yaml
replicationcontroller "redis-master" created

[root@k8s-master redis-master]# kubectl get pods
NAME                 READY     STATUS    RESTARTS   AGE
redis-master-25bpz   1/1       Running   0          13s

[root@k8s-master redis-master]# kubectl get rc
NAME           DESIRED   CURRENT   READY     AGE
redis-master   1         1         1         30s
``` 
接下来我们来写服务
```
apiVersion: v1
kind: Service
metadata:
  name:redis-master
  labels:
    name: redis-master
spec:
  ports:
  - port: 6379                              # service暴露在cluster ip上的端口，即虚拟端口
    targetPort: 6379                        # Pod上的端口
  selector:
    name: redis-master                      # 哪些Label的Pod属于此服务
```
然后启动服务
```
[root@k8s-master redis-master]# kubectl create -f redis-master-svc.yaml
service "redis-master" created

[root@k8s-master redis-master]# kubectl get services
NAME         TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.68.0.1    <none>        443/TCP   3h
redis-master   ClusterIP   10.68.69.173   <none>        6379/TCP   5s
```
这样就成功地创建了redis主服务

### redis-slave
有了redis主节点之后，我们还希望使用slave节点为主节点提供读操作。

由于IP地址是在服务创建后由Kubernetes系统自动分配的，在其他Pod中无法预先知道某个Service的虚拟IP地址，因此需要一个机制来找到这个服务。Kubernetes巧妙地使用了Linux环境变量，在每个Pod的容器里都增加了一组Service相关的环境变量，用来记录从服务名到虚拟IP地址的映射关系。以redis-master服务为例，在容器的环境变量中会增加如下两条记录
```
REDIS_MASTER_SERVICE_HOST=10.68.69.173
REDIS_MASTER_SERVICE_PORT=6379
```
然后写一个dockerfile，redis的从节点需要声明主节点
```
FROM daocloud.io/redis

MAINTAINER daba0007

ADD redis-slave.conf /etc/redis/redis.conf

WORKDIR /etc/redis/

CMD redis-server redis.conf --slaveof ${REDIS_MASTER_SERVICE_HOST} ${REDIS_MASTER_SERVICE_PORT}
```
然后创建我们slave的dockerfile，并把它push到我的仓库里
```
docker build -t daba0007/redis-slave  .
docker push daba0007/redis-slave
```
然后来编写slave的redis-slave-rc.yaml
```
apiVersion: v1
kind: ReplicationController
metadata:
  name: redis-slave
  labels:
    name: redis-slave
spec:
  replicas: 2                                   # 启动两个副本来做从服务
  selector:
    name: redis-slave
  template:
    metadata:
      labels:
        name:redis-slave
    spec:
      containers:
      - name: redis-slave
        image: daba0007/redis-slave
        env:                                    # 获取k8s环境的变量
        - name: GET_HOSTS_FROM
          value: env
        ports:
        - containerPort: 6379
```
然后执行
```bash
[root@k8s-master redis-slave]# kubectl create -f redis-slave-rc.yaml
replicationcontroller "redis-slave" created
[root@k8s-master redis-slave]# kubectl get rc
NAME           DESIRED   CURRENT   READY     AGE
redis-master   1         1         1         10h
redis-slave    2         2         1         5s
[root@k8s-master redis-slave]# kubectl get pods
NAME                 READY     STATUS    RESTARTS   AGE
redis-master-25bpz   1/1       Running   1          10h
redis-slave-plrxq    1/1       Running   0          12s
redis-slave-thb9r    1/1       Running   0          12s

```
然后再编写redis-slave-svc.yaml
```
apiVersion: v1
kind: Service
metadata:
  name: redis-slave
  labels:
    name: redis-slave
spec:
  ports:
  - port: 6379
  selector:
    name: redis-slave
```
然后执行
```
[root@k8s-master redis-slave]# kubectl create -f redis-slave-svc.yaml
service "redis-slave" created

[root@k8s-master redis-slave]# kubectl get services
NAME           TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
kubernetes     ClusterIP   10.68.0.1      <none>        443/TCP    14h
redis-master   ClusterIP   10.68.69.173   <none>        6379/TCP   10h
redis-slave    ClusterIP   10.68.174.55   <none>        6379/TCP   5s
```
看到都是running,说明启动成功，运行顺利。

### 测试
进入主节点，在主节点的上执行写入数值a=1,在从数据库读取发现得到a的值等于1,说明同步成功过，redis主从集群配置成功。
```
[root@k8s-master redis]# kubectl exec -ti redis-master-25bpz /bin/bash
root@redis-master-25bpz:/etc/redis# redis-cli
127.0.0.1:6379> set a 1
OK
127.0.0.1:6379> exit
root@redis-master-25bpz:/etc/redis# exit
exit
[root@k8s-master redis]# kubectl exec -ti redis-slave-plrxq /bin/bash
root@redis-slave-plrxq:/etc/redis# redis-cli
127.0.0.1:6379> get a
"1"
127.0.0.1:6379> exit

```
## mysql服务
接下来是将数据库mysql的k8s部署。

### 原理
mysql是一个关系型数据库管理系统，它是开源的，并且支持大型的数据库，也支持多种语言。在我们的web集群中，它主要扮演者数据存储的角色。它会将服务的数据存储到它的数据库中。当我们的服务第一次调用数据时，会到mysql中来查找数据，同时写入redis。之后若在redis上查找不到数据，会再到mysql中来查找。

### 主从
mysql的主从复制是指将Mysql的某一台主机的数据复制到其它主机（slaves）上，并重新执行一遍。复制过程中一个服务器充当主服务器，而一个或多个其它服务器充当从服务器。当一个从服务器连接主服务器时，它通知主服务器从服务器在日志中读取的最后一次成功更新的位置。从服务器接收从那时起发生的任何更新，然后封锁并等待主服务器通知新的更新。

一般在机器上，mysql的主从复制可以通过如下方式实现。
1. master

在master主机上修改配置文件，比如通常是修改my.cnf。
```
[mysqld] 
server-id=1 
log-bin
```
在mysql上创建同步账号并授权。

如下，创建用户名为test，密码为123456：
```
create user 'test'@'%' identified by '123456';
```
如下，给repl用户授权允许同步：
```
grant replication slave on *.* to 'test'@'%' identified by '123456';
```
2. slave

同样，在slave主机上修改配置文件。
```
[mysqld]
server-id=2 
log-bin
```
接着配置如下，其中x.x.x.x为master主机ip地址。
```
change master to master_host='x.x.x.x',master_user='test',master_password='123456';
```
使用k8s的话，区别其实也不是很大，只是在创建服务和镜像的时候就把内容先写好而已。
### mysql-master
在docker官网镜像文件https://hub.docker.com/_/mysql/里有两个文件Dockerfile, docker-entrypoint.sh，这里用的是5.7的版本。把它下载下来，在dockerfile中添加如下(同时修改上面一句)：
```
RUN sed -i '/\[mysqld\]/a server-id=1\nlog-bin' /etc/mysql/mysql.conf.d/mysqld.cnf
```

并在docker-entrypoint.sh中添加
```
echo "CREATE USER '$MYSQL_REPLICATION_USER'@'%' IDENTIFIED BY '$MYSQL_REPLICATION_PASSWORD' ;" | "${mysql[@]}"
echo "GRANT REPLICATION SLAVE ON *.* TO '$MYSQL_REPLICATION_USER'@'%' IDENTIFIED BY '$MYSQL_REPLICATION_PASSWORD' ;" | "${mysql[@]}"
echo 'FLUSH PRIVILEGES ;' | "${mysql[@]}"
echo
```
上面添加了两个环境变量MYSQL_REPLICATION_USER和MYSQL_REPLICATION_PASSWORD，用作主从复制的账号和密码。

然后创建镜像并且将它上传
```
docker build -t daba0007/mysql-master .
docker push daba0007/mysql-master
```
这样可以生成一个新的mysql-master的镜像提供服务

然后创建mysql-master-rc.yaml，这里我们要挂载一个database的文件夹，方便以后做数据迁移
```
apiVersion: v1
kind: ReplicationController
metadata:
  name: mysql-master
  labels:
    name: mysql-master
spec:
  replicas: 1
  selector:
    name: mysql-master
  template:
    metadata:
      labels:
        name: mysql-master
    spec:
      containers:
      - name: mysql-master
        image: daba0007/mysql-master
        volumeMounts:                                   # 挂载在容器上的数据卷
        - name: mysql-database                          # 标签
          mountPath: /etc/mysql/database                # 容器上数据卷的路径
          readOnly: false                               # 可读写
        env:
        - name: MYSQL_ROOT_PASSWORD                     # 数据库root密码
          value: "123456"
        - name: MYSQL_REPLICATION_USER                  # 提供给从数据库同步的账号
          value: "test"
        - name: MYSQL_REPLICATION_PASSWORD              # 提供给从数据库同步的账号的密码
          value: "123456"
        ports:
        - containerPort: 3306
      volumes:                                           # 挂载在主机上的数据卷
      - name: mysql-database                             # 对应标签
        hostPath:
          path: /root/k8s/mysql/mysql-master/database    # 主机上数据卷的路径
```
然后执行
```
[root@k8s-master mysql-master]# kubectl create -f mysql-master-rc.yaml
replicationcontroller "mysql-master" created

[root@k8s-master mysql-master]# kubectl get rc
NAME           DESIRED   CURRENT   READY     AGE
mysql-master   1         1         1         12s
redis-master   1         1         1         1d
redis-slave    2         2         2         1d

[root@k8s-master mysql-master]# kubectl get pods
NAME                 READY     STATUS    RESTARTS   AGE
mysql-master-whtwd   1/1       Running   0          8s
redis-master-25bpz   1/1       Running   3          2d
redis-slave-plrxq    1/1       Running   2          1d
redis-slave-thb9r    1/1       Running   2          1d

```
再编写mysql服务mysql-master-svc.yaml
```
apiVersion: v1
kind: Service
metadata:
  name: mysql-master
  labels:
    name: mysql-master
spec:
  ports:
    - port: 3306      
      targetPort: 3306 
  selector:
    name: mysql-master
```
然后创建
```bash
[root@k8s-master mysql-master]# kubectl create -f mysql-master-svc.yaml
service "mysql-master" created

NAME           TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
kubernetes     ClusterIP   10.68.0.1      <none>        443/TCP    2d
mysql-master   ClusterIP   10.68.83.79    <none>        3306/TCP   5s
redis-master   ClusterIP   10.68.69.173   <none>        6379/TCP   2d
redis-slave    ClusterIP   10.68.174.55   <none>        6379/TCP   1d

```
到这里，我们就实现了mysql主服务的创建

### mysql-slave
mysql-slave与master的创建略有不同

在dockerfile中添加如下(同时修改上面一句)：
```
RUN RAND="$(date +%s | rev | cut -c 1-2)$(echo ${RANDOM})" && sed -i '/\[mysqld\]/a server-id='$RAND'\nlog-bin' /etc/mysql/mysql.conf.d/mysqld.cnf

```
这里server-id用的是随机数。

并在docker-entrypoint.sh中添加
```
echo "STOP SLAVE;" | "${mysql[@]}"
echo "CHANGE MASTER TO master_host='$MYSQL_MASTER_SERVICE_HOST', master_user='$MYSQL_REPLICATION_USER', master_password='$MYSQL_REPLICATION_PASSWORD' ;" | "${mysql[@]}"
echo "START SLAVE;" | "${mysql[@]}"

```

上面slave的配置中，master_host 一项用的是 $MYSQL_MASTER_SERVICE_HOST，这个环境变量（enviromnent variable）是由k8s生成的。

k8s的service创建后，会自动分配一个cluster ip，这个cluster ip是动态的，我们没法直接使用或硬编码，k8s为了service对容器的可见，生成了一组环境变量，这些环境变量用于记录service name到cluster ip地址的映射关系，这样容器中就可以使用这些变量来使用service。（类似的，Docker中提供了links。）

举例：如果service的名称为foo，则生成的环境变量如下：
```
FOO_SERVICE_HOST
FOO_SERVICE_PORT
```
更多介绍请参考k8s官方资料：http://kubernetes.io/docs/user-guide/container-environment/


然后创建镜像并且上传
```
docker build -t daba0007/mysql-slave .
docker push daba0007/mysql-slave
```
然后编写mysql-slave-rc.yaml
```
apiVersion: v1
kind: ReplicationController
metadata:
  name: mysql-slave
  labels:
    name: mysql-slave
spec:
  replicas: 2
  selector:
    name: mysql-slave
  template:
    metadata:
      labels:
        name: mysql-slave
    spec:
      containers:
      - name: mysql-slave
        image: daba0007/mysql-slave
        env:
        - name: MYSQL_ROOT_PASSWORD
          value: "123456"
        - name: MYSQL_REPLICATION_USER
          value: "test"
        - name: MYSQL_REPLICATION_PASSWORD
          value: "123456"
        ports:
        - containerPort: 3306
```
然后创建
```
[root@k8s-master mysql-slave]# kubectl create -f mysql-slave-rc.yaml
replicationcontroller "mysql-slave" created

[root@k8s-master mysql-slave]# kubectl get rc
NAME           DESIRED   CURRENT   READY     AGE
mysql-master   1         1         1         22m
mysql-slave    2         2         1         7s
redis-master   1         1         1         1d
redis-slave    2         2         2         1d

[root@k8s-master mysql-slave]# kubectl get pods
NAME                 READY     STATUS    RESTARTS   AGE
mysql-master-whtwd   1/1       Running   0          1m
mysql-slave-6x8bx    1/1       Running   0          11s
mysql-slave-n58vk    1/1       Running   0          11s
redis-master-25bpz   1/1       Running   3          2d
redis-slave-plrxq    1/1       Running   2          1d
redis-slave-thb9r    1/1       Running   2          1d

```
之后编写mysql-slave-svc.yaml
```
apiVersion: v1
kind: Service
metadata:
  name: mysql-slave
  labels:
    name: mysql-slave
spec:
  ports:
    - port: 3306      
      targetPort: 3306 
  selector:
    name: mysql-slave
```
然后创建mysql-slave服务
```
[root@k8s-master mysql-slave]# kubectl create -f mysql-slave-svc.yaml
service "mysql-slave" created

[root@k8s-master mysql-slave]# kubectl get svc
NAME           TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
kubernetes     ClusterIP   10.68.0.1       <none>        443/TCP    2d
mysql-master   ClusterIP   10.68.83.79     <none>        3306/TCP   1m
mysql-slave    ClusterIP   10.68.208.186   <none>        3306/TCP   9s
redis-master   ClusterIP   10.68.69.173    <none>        6379/TCP   2d
redis-slave    ClusterIP   10.68.174.55    <none>        6379/TCP   1d

```
这样mysql-slave服务就创建成功了,来测试以下是否有同步到主库的数据

### 测试
如何证明我们已经成功地搭建了mysql主从连接了呢？

首先登录我们的主数据库,导入我们的数据库,并且查看数据库，会发现数据已经导入
```bash
[root@k8s-master mysql-slave]# kubectl exec -ti mysql-master-whtwd  /bin/bash
root@mysql-master-whtwd:/# cd /etc/mysql/database/
root@mysql-master-whtwd:/etc/mysql/database#  mysql -uroot -p -e "create database form;"      # 创建form数据库
Enter password:
root@mysql-master-whtwd:/etc/mysql/database# mysql -uroot -p form < form.sql                  # 导入我们之前的数据库
Enter password:
root@mysql-master-whtwd:/etc/mysql/database# mysql -uroot -p
Enter password:
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 12
Server version: 5.7.20-log MySQL Community Server (GPL)

Copyright (c) 2000, 2017, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql> show master status;
+-------------------------------+----------+--------------+------------------+-------------------+
| File                          | Position | Binlog_Do_DB | Binlog_Ignore_DB | Executed_Gtid_Set |
+-------------------------------+----------+--------------+------------------+-------------------+
| mysql-master-whtwd-bin.000003 |    18218 |              |                  |                   |
+-------------------------------+----------+--------------+------------------+-------------------+
1 row in set (0.01 sec)

mysql> use form;
Reading table information for completion of table and column names
You can turn off this feature to get a quicker startup with -A

Database changed
mysql> show tables;
+----------------------------+
| Tables_in_form             |
+----------------------------+
| auth_group                 |
| auth_group_permissions     |
| auth_permission            |
| auth_user                  |
| auth_user_groups           |
| auth_user_user_permissions |
| django_admin_log           |
| django_content_type        |
| django_migrations          |
| django_session             |
| form_code_data             |
| form_user                  |
| form_user_data             |
+----------------------------+
13 rows in set (0.00 sec)

```
然后查看我们的从数据库，发现从库已经连接上了主库，并且已经写入了form数据库，说明我们的mysql主从服务集群已经成功搭建。
```bash
[root@k8s-master mysql-slave]# kubectl exec -ti mysql-slave-6x8bx -- mysql -uroot -p
Enter password:
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 5
Server version: 5.7.20-log MySQL Community Server (GPL)

Copyright (c) 2000, 2017, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql> show slave status\G;
*************************** 1. row ***************************
               Slave_IO_State: Waiting for master to send event
                  Master_Host: 10.68.83.79
                  Master_User: test
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: mysql-master-whtwd-bin.000003
          Read_Master_Log_Pos: 18218
               Relay_Log_File: mysql-slave-6x8bx-relay-bin.000005
                Relay_Log_Pos: 18457
        Relay_Master_Log_File: mysql-master-whtwd-bin.000003
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
              Replicate_Do_DB:
          Replicate_Ignore_DB:
           Replicate_Do_Table:
       Replicate_Ignore_Table:
      Replicate_Wild_Do_Table:
  Replicate_Wild_Ignore_Table:
                   Last_Errno: 0
                   Last_Error:
                 Skip_Counter: 0
          Exec_Master_Log_Pos: 18218
              Relay_Log_Space: 3015257
              Until_Condition: None
               Until_Log_File:
                Until_Log_Pos: 0
           Master_SSL_Allowed: No
           Master_SSL_CA_File:
           Master_SSL_CA_Path:
              Master_SSL_Cert:
            Master_SSL_Cipher:
               Master_SSL_Key:
        Seconds_Behind_Master: 0
Master_SSL_Verify_Server_Cert: No
                Last_IO_Errno: 0
                Last_IO_Error:
               Last_SQL_Errno: 0
               Last_SQL_Error:
  Replicate_Ignore_Server_Ids:
             Master_Server_Id: 1
                  Master_UUID: 379cac8b-f626-11e7-8b34-c2a2572e0349
             Master_Info_File: /var/lib/mysql/master.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State: Slave has read all relay log; waiting for more updates
           Master_Retry_Count: 86400
                  Master_Bind:
      Last_IO_Error_Timestamp:
     Last_SQL_Error_Timestamp:
               Master_SSL_Crl:
           Master_SSL_Crlpath:
           Retrieved_Gtid_Set:
            Executed_Gtid_Set:
                Auto_Position: 0
         Replicate_Rewrite_DB:
                 Channel_Name:
           Master_TLS_Version:
1 row in set (0.00 sec)

ERROR:
No query specified

mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| form               |
| mysql              |
| performance_schema |
| sys                |
+--------------------+
5 rows in set (0.01 sec)

```
## web集群

我使用的是django做为架构来搭建web。这里web前端的内容我就不做扩展了，我还是使用上次随便写的那个网站来做测试。不过web集群在这里和docker当时的做法不太一样了。之前我们是使用了web容器和nginx容器共享数据卷容器来实现网站数据共享。

nginx是一个高性能的HTTP和反向代理服务器,在web集群中我们使用它做为http的代理服务器，在k8s中，我们完全可以把这web容器和nginx容器写在一个同一个pod里面，因为他们共享着数据卷，关系十分地亲密。

使用django连接mysql和redis服务主要是在setting中修改。
```
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'form',
        'USER':'root',
        'PASSWORD':'123456',
        #'HOST': '127.0.0.1'
        'HOST':'service_mysql',
        'Port':'3306',
   }

}
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        #"LOCATION": "redis://127.0.0.1:6379",
        "LOCATION": "redis://service_redis:6379",               
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

```
我们需要把这里host的mysql和location的redis换成服务的ip。首先来编写dockerfile
```
# 基础镜像
FROM daocloud.io/python:3.6

# 维护者信息
MAINTAINER daba0007

ADD dabaweb.tar.gz /usr/src/

# app 所在目录
WORKDIR /usr/src/dabaweb

RUN pip install xlutils

RUN pip install django-redis
# 安装 app 所需依赖
RUN pip install --no-cache-dir -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 启动执行命令
COPY entrypoint.sh /usr/src/
WORKDIR /usr/src
RUN chmod +x /usr/src/entrypoint.sh
ENTRYPOINT ["/usr/src/entrypoint.sh"]

```
这里的启动脚本如下 entrypoint.sh
```
#!/bin/bash

sed -i "s/service_mysql/$(echo $MYSQL_MASTER_SERVICE_HOST)/g" /usr/src/dabaweb/dabaweb/setting.py

sed -i "s/service_redis/$(echo $REDIS_MASTER_SERVICE_HOST)/g" /usr/src/dabaweb/dabaweb/setting.py

#使用uwsgi来启动django
/usr/local/bin/uwsgi --http :8000 --chdir /usr/src/dabaweb -w dabaweb.wsgi
```
创建dockerfile,并且上传
```
docker build -t daba0007/dabaweb  .
docker push daba0007/dabaweb
```

再构造一个nginx的dockerfile
```
FROM daba0007/nginx

MAINTAINER daba0007

RUN rm /etc/nginx/conf.d/default.conf
ADD nginx-conf/ /etc/nginx/conf.d/

```
nginx服务连接dabaweb是在nginx.conf中proxy_pass,我们需要把web替代成localhost,因为是在同一个pod中。
```
server {

    listen 80;
    server_name localhost;
    charset utf-8;
    root   /usr/src/dabaweb;
    access_log  /var/log/nginx/django.log;

    location ^~ /static {
        alias /usr/src/dabaweb/static;
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

}
```

那么我们需要挂载文件夹。编写dabacluster-rc.yaml
```
apiVersion: v1
kind: ReplicationController
metadata:
  name: dabacluster
  labels:
    name: dabacluster
spec:
  replicas: 3
  selector:
    name: dabacluster
  template:
    metadata:
      labels:
        name: dabacluster
    spec:
      containers:
      - name: dabaweb
        image: daba0007/dabaweb
        env:
        - name: GET_HOSTS_FROM
          value: env
        ports:
        - containerPort: 8000
        volumeMounts:
        - name: dabaweb-dir
          mountPath: /usr/src/dabaweb
          readOnly: false
      - name: dabanginx                                     # 这个是nginx集群，暴露80端口方便服务暴露
        image: daba0007/dabanginx
        env:
        - name: GET_HOSTS_FROM
          value: env
        ports:
        - containerPort: 80
        volumeMounts:                                       # 也要挂载这两个数据卷
        - name: dabaweb-dir
          mountPath: /usr/src/dabaweb
          readOnly: false
      volumes:
      - name: dabaweb-dir
        hostPath:
          path: /root/k8s/web/web/dabaweb/

```
然后执行
```
[root@k8s-master web]# kubectl create -f dabacluster-rc.yaml
replicationcontroller "dabacluster" created

NAME           DESIRED   CURRENT   READY     AGE
dabacluster    3         3         3         1m
mysql-master   1         1         1         1d
mysql-slave    2         2         2         1d
redis-master   1         1         1         3d
redis-slave    2         2         2         3d


[root@k8s-master web]# kubectl get pod
NAME                 READY     STATUS    RESTARTS   AGE
dabacluster-5kp26    2/2       Running   0          18s
dabacluster-7dhsk    2/2       Running   0          18s
dabacluster-mww8t    2/2       Running   0          18s
mysql-master-whtwd   1/1       Running   3          2d
mysql-slave-6x8bx    1/1       Running   3          2d
mysql-slave-n58vk    1/1       Running   3          2d
redis-master-25bpz   1/1       Running   6          4d
redis-slave-plrxq    1/1       Running   5          4d
redis-slave-thb9r    1/1       Running   5          4d

```
再编写web服务web-svc.yaml，连接服务时，使用Service的NodePort给kubernetes集群中Service映射一个外网可以访问的端口，这样一来，外部就可以通过NodeIP+NodePort的方式访问集群中的服务了。
```
apiVersion: v1
kind: Service
metadata:
  name: dabacluster
  labels:
    name: dabacluster
spec:
  ports:
    type: NodePort  
    - port: 80      
      targetPort: 80 
  nodePort: 32000                           # 指明暴露在外端口的port，即k8s中的80映射到主机上32000端口  
  selector:
    name: dabacluster
```
然后执行
```
[root@k8s-master web]# kubectl create -f dabacluster-svc.yaml
service "dabacluster" created

NAME           TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
dabacluster    NodePort    10.68.64.177    <none>        80:32000/TCP   10m
kubernetes     ClusterIP   10.68.0.1       <none>        443/TCP        4d
mysql-master   ClusterIP   10.68.83.79     <none>        3306/TCP       2d
mysql-slave    ClusterIP   10.68.208.186   <none>        3306/TCP       2d
redis-master   ClusterIP   10.68.69.173    <none>        6379/TCP       4d
redis-slave    ClusterIP   10.68.174.55    <none>        6379/TCP       4d
```
### 测试
访问http://ip:32000,发现成功的访问，说明服务启动成功

## 节点
花了两大篇来介绍k8s,细心的人就会发现我们只说到了svc,rc和pod。我们之前构造k8s的时候是使用了三个节点，一个master和两个minion,在搭建web集群的过程中完全没提到啊，它们发生了什么？

其实对于每个节点(在我的集群中是三个，一个master和两个minion),他们负载的能力肯定是有限的。我们在每次写服务的时候，都会分配一些资源给节点。当一个节点的负载超额的时候（pod数量过多或系统资源不够分配），k8s会自动加入下一个节点，并且将这些超出的pod放到下一个节点中。也就是说，如果我们有足够多的节点，在master上操作的时候就感觉像是在一个超级计算机中，所有的需求都能满足。


### 一些常见的检查错误命令
进入某个节点查看
```
kubectl exec -ti mysql-master-whtwd  /bin/bash
```
得到log
```
kubectl logs -f [pods]                          # [pods]写入你pods的名字,也可以是rc,svc等等
```
删除
```
kubectl delete svc redis-master
kubectl delete rc redis-master
```

感谢以下博主提供的思路
>1. https://www.kubernetes.org.cn/3265.html
>2. http://blog.csdn.net/test103/article/details/55663562
>3. https://my.oschina.net/FrankXin/blog/875414
>4. https://www.jianshu.com/p/509b65e9a4f5
