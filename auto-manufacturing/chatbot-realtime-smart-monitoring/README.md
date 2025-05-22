# Chatbot for Realtime Smart Monitoring
=================================

## Authors:
- [Rafael Caixeta](https://www.linkedin.com/in/rafaelcaixeta/) @caixeta
- [Alejandro Cayo](https://www.linkedin.com/in/alejandro-c-6623491a9) @acayo
- [Nikhil Parekh](https://www.linkedin.com/in/parekhn/) @nikpaws 
- [Bichitresh Saha](https://www.linkedin.com/in/bichitresh-saha/) @btsaha

# Prerequisites
===============
* Deploy this infrastructure in the us-east-1 region
* [node](https://nodejs.org/en) >= 16.0.0
* [npm](https://www.npmjs.com/) >= 8.0.0
* [AWS CLI](https://aws.amazon.com/cli/) >= 2.0.0
* [AWS CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-construct-library.html) >= 2.127.0


## Setup AWS Infratructure

1. Install NPM Packages

    ```bash
    npm i
    ```

2. Generate the template

    ```bash
    cdk synth -q
    ```

3. Bootstrap your AWS Account for CDK (*This only needs to be done once for a AWS Account. If you already bootstrap your AWS Account for CDK you can skip this step.*)

    ```bash
    cdk bootstrap
    ```

4. Deploy to your AWS Account in context (*Make sure you correctly configure AWS CLI and have a profile and region set*)

    ```bash
    cdk deploy roles-stack --require-approval=never
    cdk deploy opensearch-stack --require-approval=never
    cdk deploy bedrock-stack --require-approval=never
    ```

    - Copy the PDF files from `auto-manufacturing/chatbot-realtime-smart-monitoring/sampledocs` folder to the s3 bucket created by the bedrock-stack. The bucket name can be found under the outputs tab for the stack with a key name 'kbbucketname'.
    - After uploading the files, go to the Bedrock Service. Under Knowledge Bases, select the 'mfg-kb' knowledge base, select the Data Source 'diagnostics-kb-datasource' and click on the 'Sync' button. 
    
    ```bash
    cdk deploy api-stack --require-approval=never
    cdk deploy ui-stack --require-approval=never
    ```

5. Update and Upload the UI files

    - Open the `auto-manufacturing/chatbot-realtime-smart-monitoring/static-site/chatbot.html` file and update the API_ENDPOINT URL hostname with the hostname shown ApiEndpoint key in the output tab of the api-stack CloudFormation stack. 
    - Copy all files from the `auto-manufacturing/chatbot-realtime-smart-monitoring/static-site/` folder to the s3 bucket created by the ui-stack. The bucket name can be found under the outputs tab for the stack with the key name 'smartmons3bucketname'
    - Finally, you can access the UI file by launching the URL for the CloudFront distribution deployed by the ui-stack. The URL can be found under the outputs tab under the key 'smartmoncdnurl'

# How to delete

From within the root project folder (``auto-manufacturing``), run the following command:

```sh
cdk destroy --force --all
```

**Note - if you created any aliases/versions within your agent you would have to manually delete it in the console.**
