import os
import json
import datetime
import time
import finnhub
import boto3
import pandas as pd

def input_data_cleaner(input_data):
  # Convert the list of lists string to a proper list of lists
  input_data = input_data[1:-2]
  data_list = []
  for item in list(input_data.split("],")):
    item = item[1:]
    item = item.split(",")
    item = list(item)
    data_list.append(item)

  df = pd.DataFrame(data_list[1:], columns=data_list[0])

  # Convert appropriate strings to proper type
  for ind in df.index:
    df["user_id"][ind] = int(df["user_id"][ind])
    df["quantity"][ind] = int(df["quantity"][ind])
    df["price"][ind] = float(df["price"][ind])
    
  return df

def GetFinnhubClient(secret_id):
  client = boto3.client('secretsmanager')
  finnhub_api_key = client.get_secret_value(SecretId='finnhub_api_key')["SecretString"]
  finnhub_client = finnhub.Client(api_key=finnhub_api_key)
  return finnhub_client

def UpdateDataList(df,finnhub_client):
  current = int(time.time())
  current_price_list = []
  for ind in df.index:
    quoteinfo = finnhub_client.quote(df["stock symbol"][ind])
    if quoteinfo['c'] == 0:
      print("ERROR: finnhub quote call for {} returned null values, data not found".format(df["stock symbol"][ind]))

    print("INFO: Retrieved {} quote from finnhub: {}".format(df["stock symbol"][ind], str(quoteinfo)))

    current_price_list.append(quoteinfo["c"])
  
  print(str(current_price_list))
  df['current price']=current_price_list
  return df

def GetBalance(df):
  balance = 0
  for ind in df.index:   
    change = round(df["quantity"][ind] * (df["current price"][ind] - df["price"][ind]))
    if df["buy/sell"][ind] == "buy":
      balance += change
    elif df["buy/sell"][ind] == "sell":
      balance -= change
  
  pd.set_option("display.max_rows", None, "display.max_columns", None)
  print("INFO: Processed Data Structure:\n{}".format(df))    

  return balance

def UploadToS3(account_id,balance,bucket_name):
    #Write balance to (acount_id)_balance.txt and upload to s3
    file_name = account_id+"_balance.txt"
    file = open("/tmp/"+file_name, 'w')
    file.write(str(balance))
    file.close()
    
    s3_client = boto3.client('s3')
    s3_client.upload_file("/tmp/"+file_name, bucket_name, file_name)
    print("INFO: {} has been uploaded to {}".format(file_name,bucket_name))
    os.remove("/tmp/"+file_name)



def lambda_handler(event, context):
    #Below is the format SQS must receive the data in:
    #input_data = "[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:65],[12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]"

    input_data = event["Records"][0]["body"]
    
    #Cleans and properly formats input_data
    df = input_data_cleaner(input_data)
    
    #Pull Finnhub API key and intialize finnhub_client
    secret_id ="finnhub_api_key"
    finnhub_client = GetFinnhubClient(secret_id)

    #Adds current price to data_list
    df = UpdateDataList(df,finnhub_client)
    
    #Evaluate current prices and evaluates balance (profit/loss)
    balance = GetBalance(df)
    
    #Adds (user_id)_balance.txt to s3 bucket
    user_id=str(df["user_id"][0])
    bucket_name = "tf-ple-member-balance-bucket"
    UploadToS3(user_id,balance,bucket_name)
 
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