import json
import datetime
import time
import finnhub
import boto3
import os

def input_data_cleaner(input_data):
  # Convert the list of lists string to a proper list of lists
  input_data = input_data[1:-2]
  data_list = []
  for item in list(input_data.split("],")):
    item = item[1:]
    item = item.split(",")
    item = list(item)
    data_list.append(item)

  # Convert appropriate strings to proper type
  for item in data_list[1:]:
    item[0] = int(item[0])
    item[3] = int(item[3])
    item[4] = float(item[4])
  return data_list

def lambda_handler(event, context):
    #Below is the format SQS must receive the data in:
    #testdata = "[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:65],[12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]"

    input_data = event["Records"][0]["body"]

    data_list = input_data_cleaner(input_data)
  
    # Get Finnhub API key Secret Value
    client = boto3.client('secretsmanager')
    finnhub_api_key = client.get_secret_value(SecretId='finnhub_api_key')["SecretString"]
    finnhub_client = finnhub.Client(api_key=finnhub_api_key)

    balance = 0
    data_list[0].append("current price")
    current = int(time.time())

    for transaction in data_list[1:]:   
      #Add data to new "current price" column     
      quoteinfo = finnhub_client.quote(transaction[2])
      while quoteinfo['c'] == 0:
        quoteinfo = finnhub_client.quote(transaction[2])

      print("INFO: Retrieved "+transaction[2]+" quote from finnhub: " + str(quoteinfo))

      transaction.append(quoteinfo["c"])

      #Edit Balance   change = quantity * (current price-old price)
      change = round(transaction[3] * (transaction[6] - transaction[4]),2)
      if transaction[1] == "buy":
        balance += change
      elif transaction[1] == "sell":
        balance -= change


    data_list_string = '\n'.join([str("  "+str(elem)) for elem in data_list])
    print("INFO: Processed Data Structure:\n"+data_list_string)    
    
    #Write balance to (acount_id)_balance.txt and upload to s3
    account_id = str(data_list[1][0])
    file_name = account_id+"_balance.txt"
    file = open("/tmp/"+file_name, 'w')
    file.write(str(balance))
    file.close()
    
    s3_client = boto3.client('s3')
    s3_client.upload_file("/tmp/"+file_name, "tf-ple-member-balance-bucket", file_name)
    print(file_name+" has been uploaded to tf-ple-member-balance-bucket")
    os.remove("/tmp/"+file_name)

    

    return {
      'statusCode': 200,
      'balance': round(balance,2),
    }



event = {
  "Records": [
    {
      "messageId": "19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
      "receiptHandle": "MessageReceiptHandle",
      "body": "[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:65],[12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]",
      "attributes": {
        "ApproximateReceiveCount": "1",
        "SentTimestamp": "1523232000000",
        "SenderId": "123456789012",
        "ApproximateFirstReceiveTimestamp": "1523232000001"
      },
      "messageAttributes": {},
      "md5OfBody": "{{{md5_of_body}}}",
      "eventSource": "aws:sqs",
      "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:MyQueue",
      "awsRegion": "us-east-1"
    }
  ]
}

#print(lambda_handler(event,2))