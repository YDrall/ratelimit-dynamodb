### Multi-region & Distributed Rate limiting system using Dynamodb

#### Note: This repository provides an outline of the overall design and architecture and only for demo purposes at the moment.

#### Requirements:

* Fast and scalable.
* Available over multiple regions.
* Low latency.
* Relaxing rate limit(if rate limit is 50 then 50 to 54/55 request may happen).

#### Approach:

The approach will be similar to sliding logs architecture. It works as follow:

1. We will use a hashmap with key as user id and value will a sorted list of the timestamps of every request. It will look like this:

```
{
    "user_id_1": ['2020-03-21 22:01:41.654205', '2020-03-21 22:01:41.754205', '2020-03-21 22:01:41.854205']
}
```

2. For every request we will find all timestamps greater than current time - timedelta(seconds=time_limit_in_seconds) of given user.
3. If length of returned list is greater than the rate limit then we will not allow the request, otherwise we will allow the request
4. We will also keep deleting older keys from list using another periodic async job.


#### Challenges:

1. A fast way to store and access the list of timestamps of a user including filtering.
2. Data should be available to every region with minimum latency.


#### Solution:

For problem #1, we can use a in-memory data store.

Redis looks like the most convenient and fast way to perform all required options. We can use sorted set in Redis, it allows O(logn) insertion, search and deletions of timestamps values of a given key. The only problem with this solution is the multi-region availability of the Redis cluster with a low latency.

For problem #2, A simple approach is to have only one cluster in a specific region but it will have very high latency in other regions. To solve this we may need to add one cluster in every region. Then the problem will to make data available in every other cluster.

Well we may able to achieve it using some approaches like write to all the cluster in every region on every request either synchronously or asynchronously. But it all requires a lot more code, complexities and increase in overall cost.


#### Why dynamodb?

It solve problem #1 and #2 easily with no extra complexities.

1. We can make user id has hash key of table and timestamps as range keys of the table. It has similar time complexities as of Redis's sorted array. But the only downside is that the data is store in SSDs instead of RAM.
2. Dynamodb allows global tables, means we can select the regions for which we wants the table available and it is fully managed by AWS so we do not need to worry about data availability across the regions.


#### Additional Requirements

1. Support hourly limits. 1000 per hour
2. Support per month limits. 20K per month

Our solution will be able to handle hourly as well as monthly rate limit pretty well. But the only concern here is the count of rate, because rate is deciding the size of the timestamps list, if the range is too high, then we will be fetching a lots of data from the database and it will not be very efficient.

The per hour, per month or per year rate should be handled intelligently, because storing all the timestamps for such a large period of time is not going to be optimal(neither space wise nor time wise).

Applying a time range buckets can work here. Say for hourly limits, we can make buckets of 10 minutes and in each bucket we will store the number of request during the time range.

Implementation of this bucket approach in dynamodb:


1. Create buckets with user id as primary hash key and bucket timestamp as range key. In addition every column will have the request count value too.
2. Now query the table for last n buckets and add the requests count of all the buckets.
3. Step 2 can be performed asynchronously. We can do it by running a periodic job every n seconds. This periodic job will create buckets by reading the timestamp of last n seconds.

This repository is handling both hourly and monthly limits as well inside single table of database. Look at the sample implementation in app.py file.


### Challenge #2

A third-party has a limit of 100 per second. This limit applies to the project, which means
it has to be used across all 200 customers.

Approach:

* First come first serve: We can keep serving the user until we hit the limit bounds. The downside of the approach is that few user can use up all the limit and other users will always get limit shortage error.
* Upper limit per user: This is an optimization on above approach. We can put an upper limit for each user. A user can't cross its upper limit.
* Priority Queue: Queue all the requests in a queue and set prioritise users based on requests of user in last 1 second.


##### Priority Queue Based processing:

* We can keep the count of user's requests in last 1 second using the rate limiting approach.
* For priority queue we will use sorted sets in Redis. The user id will be the key and value will be calculated as follows (third party api limit - user's request count of last 1 second). So the user will maximum quota left will be front of queue.
* A job to process the request queue and put the result in db or somehow let client know that the request is complete.
* The job will first check if the api quota is remaining or not, if no quota is left then mark all items in the queues as failed. otherwise keep processing the queue until the rate limit is over or queue becomes empty.
