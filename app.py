import os
from datetime import datetime, timedelta

from dynamodb import DynamoDb

TABLE_NAME = os.environ.get('RATE_LIMIT_TABLE')
SECONDS_RATE_LIMIT = os.environ.get('SECONDS_RATE_LIMIT', 50)
HOURLY_RATE_LIMIT = os.environ.get('HOURLY_RATE_LIMIT', 1000)
MONTHLY_RATE_LIMIT = os.environ.get('MONTHLY_RATE_LIMIT', 20000)
HOURLY_BUCKET_SIZE_IN_SECONDS = os.environ.get('HOURLY_BUCKET_SIZE_IN_SECONDS', 600)
MONTHLY_BUCKET_SIZE_IN_SECONDS = os.environ.get('HOURLY_BUCKET_SIZE_IN_SECONDS', 3600*24)


SECONDS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
HOURLY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
MONTHLY_TIMESTAMP_FORMAT = "%Y-%m-%d %H"


def check_rate_limit(user_id):
    db = DynamoDb()
    utc_time = datetime.utcnow()
    hash_key = 'user_id'
    range_key = 'timestamp'
    seconds_records = db.query_range(TABLE_NAME, hash_key, user_id,
                                     range_key, utc_time - timedelta(seconds=1), utc_time).get('Items')

    # seconds_records = list(filter(lambda x: x.get('hourly_count', 0) == 0 and
    #                                         x.get('yearly_count', 0) == 0, seconds_records))
    if len(seconds_records) > SECONDS_RATE_LIMIT:
        return False

    hourly_records = db.query_range(TABLE_NAME, hash_key, user_id,
                                    range_key, utc_time - timedelta(seconds=3600), utc_time,
                                    ).get('Items')
    total_hourly_count = 0
    for hr in hourly_records:
        total_hourly_count += hr.get('hourly_count', 0)
    if total_hourly_count + len(seconds_records) > HOURLY_RATE_LIMIT:
        return False

    monthly_records = db.query_range(TABLE_NAME, hash_key, user_id,
                                     range_key, utc_time - timedelta(seconds=3600 * 24), utc_time,
                                     ).get('Items')
    total_monthly_count = 0
    for mr in monthly_records:
        total_monthly_count += mr.get('monthly_count', 0)

    if total_monthly_count + total_hourly_count + len(seconds_records) > MONTHLY_RATE_LIMIT:
        return False
    db.add(TABLE_NAME, hash_key, user_id, range_key,
           datetime.strftime(utc_time, SECONDS_TIMESTAMP_FORMAT), hourly_count=0, monthly_count=0)
    return True


def create_hour_batch(user_id):
    """
    Run periodically to create hour batch.
    :param user_id:
    :return:
    """
    db = DynamoDb()
    utc_time = datetime.utcnow()
    hash_key = 'user_id'
    range_key = 'timestamp'

    records = db.query_range(TABLE_NAME, hash_key, user_id, range_key,
                             utc_time - timedelta(seconds=HOURLY_BUCKET_SIZE_IN_SECONDS),
                             utc_time - timedelta(seconds=1)).get('Items')
    request_count = len(records)
    for record in records:
        pk_dict = {
            'user_id': record.get('user_id'),
            'timestamp': record.get('timestamp')
        }
        db.delete(TABLE_NAME, **pk_dict)
    db.add(TABLE_NAME, hash_key, user_id, range_key,
           datetime.strftime(utc_time, HOURLY_TIMESTAMP_FORMAT), hourly_count=request_count, monthly_count=0)


def create_month_batch(user_id):
    """
    Run periodically to create hour batch.
    :param user_id:
    :return:
    """
    db = DynamoDb()
    utc_time = datetime.utcnow()
    hash_key = 'user_id'
    range_key = 'timestamp'

    records = db.query_range(TABLE_NAME, hash_key, user_id, range_key,
                             utc_time - timedelta(seconds=MONTHLY_BUCKET_SIZE_IN_SECONDS),
                             utc_time - timedelta(seconds=HOURLY_BUCKET_SIZE_IN_SECONDS)).get('Items')
    request_count = len(records)
    for record in records:
        pk_dict = {
            'user_id': record.get('user_id'),
            'timestamp': record.get('timestamp')
        }
        db.delete(TABLE_NAME, **pk_dict)
    db.add(TABLE_NAME, hash_key, user_id, range_key,
           datetime.strftime(utc_time, MONTHLY_TIMESTAMP_FORMAT), hourly_count=0, monthly_count=request_count)
