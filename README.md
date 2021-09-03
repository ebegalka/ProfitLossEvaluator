# ProfitLossEvaluator

How to implement:
* Install and Configure Terraform (https://learn.hashicorp.com/collections/terraform/aws-get-started)
* Using an admin role, or a role with necessary permissions, and substitute EthanAdminUser in the code with your role/user. (This is required for managing the KMS key via terraform)
* `terraform init`
* `terraform plan`
* `terraform apply`
* Create a secret called "finnhub_api_key", include your API key from https://finnhub.io/, then configure the secret to be secured by the KMS key "tf_ple_kms_key" 

Assumptions:
* SQS input data is in this format: `[[user_id,buy/sell,stock symbol,quantity,price,timestamp(UTC)],[12345,buy,AAPL,10,76.60,2020-01-02 16:01:23],[12345,buy,AAPL,5,95.11,2020-06-05 15:21:65],[12345,buy,GME,5,20.99,2020-12-21 15:45:24],[12345,sell,GME,5,145.04,2021-01-26 18:34:12]]`
* Input Data is retrieved for 1 user at a time, user_id will not be unique
* There is no error checking for if they have sufficient funds to purchase stock, or if sufficient stock to sell

Enhancements on deck:
* Output sending mechanism, sending to an output queue or bucket maybe
* New mechanism for sending the SQS message, CSV in an S3 perhaps
* Pandas instead of list of lists

Features potentially outside constraints:
* Transaction IDs so the input data could be json format would be most ideal
