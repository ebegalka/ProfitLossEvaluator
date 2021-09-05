# ProfitLossEvaluator

Core Mission Statement:
* Receive stock transaction data, calculate user's profit/loss, and send it to be used by other services

Architecture Overview:
* SQS receives message
* Lambda function via Python processes message, calculates profit/loss (balance)
* S3 stores the balance under a file in a .txt file

Implementation Guide:
* Install and Configure Terraform (https://learn.hashicorp.com/collections/terraform/aws-get-started)
* Using an admin role, or a role with necessary permissions, substitute EthanAdminUser in the code with your role/user. (This is required for managing the KMS key via terraform). WARNING: If this is not done before implementation, the kms key may need to be re-configured by the root user.
* `terraform init`
* `terraform plan`
* `terraform apply`
* Create a secret called "finnhub_api_key", include your API key from https://finnhub.io/, then configure the secret to be secured by the KMS key "tf_ple_kms_key" 

Assumptions:
* The test data initially provided has an error in it- the time of `15:21:65`, specifically the 65 seconds, is an ivalid time. For the puposes of the testing, the time will be replaced with `15:21:55`
* Admin role/user already exists to create this infrastructure
* SQS input data is in this format(note the absence of quotes and spaces other than for timestamp): `{"StartTime":"2020-12-21 15:45:24","EndTime":"2021-09-03 12:00:00","TransactionData":"[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:55],12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]"}`
* Input Data is retrieved for 1 user at a time, user_id will not be unique
* There is no error checking for if they have sufficient funds to purchase stock, or if sufficient stock to sell
* Rounding will be shown/applied in other parts of the application- there is no rounding in this solution
* 1 Day Resolution, and pulling the stock's close for that day, is an acceptable margin of error. This compromise is a result of finnhub's limit for the free trier. 
* No manipulating the data set. For example, no adding a transaction ID, no reformatting the table into JSON for example- keep it relational.

Potential Enhancements:
* (DONE) Output sending mechanism, sending to an output queue or bucket maybe
* (DONE) Pandas instead of list of lists
* New mechanism for sending the SQS message, SQS message instructing lambda to look at a CSV in an S3 perhaps 
* Terraform state file management

Features potentially outside constraints:
* Transaction IDs so the input data could be json format would be most ideal
