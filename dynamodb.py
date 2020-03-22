import os
from boto3 import resource
from boto3.dynamodb.conditions import Key


class DynamoDb:
    def __init__(self):
        region_name = os.environ.get("REGION")
        endpoint_url = os.environ.get("DYNAMO_ENDPOINT")
        self.dynamodb_resource = resource(
            'dynamodb', region_name=region_name, endpoint_url=endpoint_url)

    def get_metadata(self, table_name):
        table = self.dynamodb_resource.Table(table_name)
        return table

    def get(self, table_name, has_key, hash_value, range_key, range_value):
        key = {}
        if has_key:
            key[has_key] = hash_value
        if range_key:
            key[range_key] = range_value
        table = self.dynamodb_resource.Table(table_name)
        response = table.get_item(Key=key)
        return response

    def add(self, table_name, hash_key, hash_value, range_key, range_value, **kwargs):
        kwargs.pop(hash_key, None)
        item = kwargs
        item[hash_key] = hash_value
        if range_key:
            item[range_key] = range_value
        table = self.dynamodb_resource.Table(table_name)
        response = table.put_item(Item=item)
        return response

    def delete(self, table_name, pk_dict):
        table = self.dynamodb_resource.Table(table_name)
        table.delete_item(Key=pk_dict)
        return True

    def query(self, table_name, query_dict):
        filter_exp = None
        for key, value in query_dict.items():
            if filter_exp:
                filter_exp = filter_exp & Key(key).eq(value)
            else:
                filter_exp = Key(key).eq(value)
        table = self.dynamodb_resource.Table(table_name)
        response = table.query(KeyConditionExpression=filter_exp)
        return response

    def query_range(self, table_name, hash_key, hash_value,
                    range_key, low_value, high_value, index_name=None):
        filter_exp = Key(hash_key).eq(hash_value) & Key(range_key).between(low_value, high_value)
        table = self.dynamodb_resource.Table(table_name)
        if index_name:
            response = table.query(IndexName=index_name, KeyConditionExpression=filter_exp)
        else:
            response = table.query(KeyConditionExpression=filter_exp)
        return response

    def update(self, table_name, pk_dict, col_dict):
        expression_vals = {}
        update_expression = 'SET '
        attr_names = {}
        for key, value in col_dict.items():
            expression_vals[':{}'.format(key)] = value
            attr_names['{}'.format(key)] = key
            update_expression += '{} = :{}, '.format(key, key)
        update_expression = update_expression.rstrip(", ")
        table = self.dynamodb_resource.Table(table_name)
        return table.update_item(
            Key=pk_dict,
            ExpressionAttributeValues=expression_vals,
            UpdateExpression=update_expression,
            ReturnValues="UPDATED_NEW"
        )
