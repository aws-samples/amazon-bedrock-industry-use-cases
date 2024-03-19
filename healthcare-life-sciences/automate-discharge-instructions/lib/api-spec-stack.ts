import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';

export class ApiSpecStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props: any) {
    super(scope, id, props);

    const apiSpecBucket = new s3.Bucket(this, 'api-spec-bucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new cdk.CfnOutput(this, 'apiSpecBucketName', {
      value: apiSpecBucket.bucketName,
      exportName: 'apiSpecBucketName',
    });
  }
}
