import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cf from 'aws-cdk-lib/aws-cloudfront';
import * as cfo from 'aws-cdk-lib/aws-cloudfront-origins';

export class UIStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const bucket = new s3.Bucket(this, 'smart-mon-static-bucket', {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const oac = new cf.S3OriginAccessControl(this, 'smart-mon-cdn-oac', { originAccessControlName: `smart-mon-oac` });
    const distribution = new cf.Distribution(this, 'smart-mon-cdn', {
      httpVersion: cf.HttpVersion.HTTP2_AND_3,
      priceClass: cf.PriceClass.PRICE_CLASS_ALL,
      enableIpv6: true,
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: cfo.S3BucketOrigin.withOriginAccessControl(bucket, {
          originAccessControl: oac,
        }),
        allowedMethods: cf.AllowedMethods.ALLOW_GET_HEAD,
        cachedMethods: cf.CachedMethods.CACHE_GET_HEAD,
        compress: true,
        viewerProtocolPolicy: cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
      ],
    });

    new cdk.CfnOutput(this, 'smart-mon-s3-bucket-name', { value: bucket.bucketName });
    new cdk.CfnOutput(this, 'smart-mon-cdn-url', { value: `https://${distribution.distributionDomainName}` });
  }
}
