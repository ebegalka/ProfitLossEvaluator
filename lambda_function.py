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
    df["timestamp(UTC)"][ind] = int(datetime.datetime.strptime(df["timestamp(UTC)"][ind], "%Y-%m-%d %H:%M:%S").timestamp())
    
  return df

def GetFinnhubClient(secret_id):
  secrets_manager_client = boto3.client('secretsmanager')
  finnhub_api_key = secrets_manager_client.get_secret_value(SecretId='finnhub_api_key')["SecretString"]
  finnhub_client = finnhub.Client(api_key=finnhub_api_key)
  return finnhub_client

def UpdateDataList(df,finnhub_client,start_time,end_time):
  #Convert string times to POSIX timestamp
  start_price_list = []
  end_price_list = []
  for ind in df.index:
    start_candleinfo = finnhub_client.stock_candles(df["stock symbol"][ind],"D",start_time,start_time)
    end_candleinfo = finnhub_client.stock_candles(df["stock symbol"][ind],"D",end_time,end_time)
    if start_candleinfo['s'] != "ok":
      print("ERROR: finnhub quote call for {} at StartTime of {} returned null values, data not found".format(df["stock symbol"][ind],start_time))
    if end_candleinfo['s'] != "ok":
      print("ERROR: finnhub quote call for {} at StartTime of {} returned null values, data not found".format(df["stock symbol"][ind],end_time))

    print("INFO: Retrieved {} stockcandle of start time {} from finnhub: {}".format(df["stock symbol"][ind], start_time, str(start_candleinfo)))
    print("INFO: Retrieved {} stockcandle of end time {} from finnhub: {}".format(df["stock symbol"][ind], end_time, str(end_candleinfo)))

    start_price_list.append(start_candleinfo["c"][0])
    end_price_list.append(end_candleinfo["c"][0])
  
  df['start price']=start_price_list
  df['end price']=end_price_list
  return df

def GetBalance(df,start_time,end_time):
  balance = 0
  for ind in df.index:
    transaction_identifier = "{} {} {} at ${}".format(df["buy/sell"][ind],str(df["quantity"][ind]),df["stock symbol"][ind],str(df["price"][ind]))
    if start_time <= df["timestamp(UTC)"][ind] <=  end_time:
      if df["buy/sell"][ind] == "buy":
        # change = end of time frame price - price it was bought for
        change = df["quantity"][ind] * (df["end price"][ind] - df["price"][ind])
        print("INFO: The transaction '{} has been processed and will result in a change of: {}".format(transaction_identifier, str(change)))

      elif df["buy/sell"][ind] == "sell":
        #find the avg buy price
        stock_total_cost = 0
        stock_total_units_bought = 0
        change = 0
        for ind2 in df.index:
          if df["buy/sell"][ind2] == "buy" and df["stock symbol"][ind2] == df["stock symbol"][ind]:
            stock_total_cost += df["price"][ind2] * df["quantity"][ind2]
            stock_total_units_bought += df["quantity"][ind2]
            #subtract the profit/loss that the user wouldve had if they held
            change -= df["quantity"][ind2] * (df["end price"][ind2] - df["price"][ind2])
        stock_avg_buy_price = stock_total_cost/stock_total_units_bought
        #change += sell price - avg buy price
        change += df["quantity"][ind] * (df["price"][ind] - stock_avg_buy_price)
        print("INFO: The transaction '{}, originally bought for ${}' has been processed and will result in a change correction of: {}".format(transaction_identifier, stock_avg_buy_price, str(change)))

      balance += change
      
    else:
      print("INFO: The transaction '{}' is out of time constraints and will not be processed".format(transaction_identifier))
  
  pd.set_option("display.max_rows", None, "display.max_columns", None)
  print("INFO: Processed Data Structure:\n{}".format(df))    

  return balance

def UploadToS3(user_id,start_time,end_time,balance,bucket_name):
    #Write balance to (acount_id)_balance.txt and upload to s3
    file_name = "{}_{}_{}_balance.txt".format(user_id,start_time,end_time)
    file = open("/tmp/"+file_name, 'w')
    file.write(str(balance))
    file.close()
    
    s3_client = boto3.client('s3')
    s3_client.upload_file("/tmp/"+file_name, bucket_name, file_name)
    print("INFO: {} has been uploaded to {}".format(file_name,bucket_name))
    os.remove("/tmp/"+file_name)



def lambda_handler(event, context):
    #Below is the format SQS must receive the data in:
    #input_data={"StartTime":"2020-12-21 15:45:24","EndTime":"2021-09-03 12:00:00","TransactionData":"[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:55],12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]"}

    input_data = json.loads(event["Records"][0]["body"])

    #Converted to POSIX time
    start_time = int(datetime.datetime.strptime(input_data["StartTime"], "%Y-%m-%d %H:%M:%S").timestamp())
    end_time = int(datetime.datetime.strptime(input_data["EndTime"], "%Y-%m-%d %H:%M:%S").timestamp())

    #Cleans and properly formats input_data
    df = input_data_cleaner(input_data["TransactionData"])
    
    #Pull Finnhub API key and intialize finnhub_client
    secret_id ="finnhub_api_key"
    finnhub_client = GetFinnhubClient(secret_id)

    #Adds current price to data_list
    df = UpdateDataList(df,finnhub_client,start_time,end_time)
    
    #Evaluate current prices and evaluates balance (profit/loss)
    balance = GetBalance(df,start_time,end_time)
    
    #Adds (user_id)_balance.txt to s3 bucket
    user_id=str(df["user_id"][0])
    bucket_name = "tf-ple-user-balance-bucket"
    UploadToS3(user_id,start_time,end_time,balance,bucket_name)
 
    return {
      'statusCode': 200,
      'balance': balance,
    }

event = {
  "Records": [
    {
      "messageId": "e85b2d89-85fb-42cc-a6b0-a60ebb53729c",
      "receiptHandle": "AQEBPCbN1doXEpANboMHYkFLrGPPalW8s+epJn+NjwK+TTf8VDWfCch3sj9fYbrFs5JKr526xO6aXO1Ww5+MSMaK3iFj5LEuQP6CCP4uqYztBHsFC7SyajShwkIUOP5zAMs0o4IpRmkXiOyQCPvKi9LRgFXujbKKiErAaiGgKW2F+JM2FHDm8OLStXmZk8ehW4C5VE2oayWTGxFUF6XiBYWTcgBSMeIIGAY0oDqZ6NxJY+8avf+/v7kZRLyyZryTDb7vy50POIKOo7NoBIg7v9RLFk0JmwO8OMiOlT8+xGdnY74lJ0vUIlDoZ1hrgg+Mhv28d/B8NygasO/wEvB792pIWB9EQ7Lo+adhzg8+UTkAK5FkIvyP7Lv1BGaIZizDwxSAg/jHSRsU3jjpgOHpj1wxEQ==",
      "body": "{\"StartTime\":\"2020-12-21 15:45:24\",\"EndTime\":\"2021-09-03 12:00:00\",\"TransactionData\":\"[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:55],12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]\"}",
      "attributes": {
        "ApproximateReceiveCount": "1",
        "SentTimestamp": "1630796278060",
        "SenderId": "AIDATMRRHSMQDUXKMTAKC",
        "ApproximateFirstReceiveTimestamp": "1630796278065"
      },
      "messageAttributes": {},
      "md5OfBody": "252c089e4b69eb5270a415ce804302d2",
      "eventSource": "aws:sqs",
      "eventSourceARN": "arn:aws:sqs:us-east-1:233105232672:terraform-example-queue",
      "awsRegion": "us-east-1"
    }
  ]
}