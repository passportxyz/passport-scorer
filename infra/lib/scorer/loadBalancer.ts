import * as aws from "@pulumi/aws";
import { Input } from "@pulumi/pulumi";

import { Topic } from "@pulumi/aws/sns";

export type AlarmConfigurations = {
  targetResponseTime: number;
  percentHTTPCodeTarget4XX: number; // percentage value for target error codes
  percentHTTPCodeTarget5XX: number; // percentage value for target error codes
  percentHTTPCodeELB4XX: number; // percentage value for ELB error codes
  percentHTTPCodeELB5XX: number; // percentage value for ELB error codes
  indexerErrorThreshold: number; // threshold for indexer logged errors
  indexerErrorPeriod: number; // period for reporting indexer logged errors
};

export function createLoadBalancerAlarms(
  name: string,
  albArnSuffix: Input<string>,
  loadBalancerAlarmThresholds: AlarmConfigurations,
  alertTopic?: Topic
) {
  if (alertTopic) {
    const metricNamespace = "AWS/ApplicationELB";
    /*
     * Alarm for monitoring ELB 5XX errors
     */
    const http5xxElbAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-ELB-5XX-${name}`,
      {
        tags: { name: `HTTP-ELB-5XX-${name}` },
        name: `HTTP-ELB-5XX-${name}`,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_ELB_5XX_Count",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of elb 5XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeELB5XX,
      }
    );

    /*
     * Alarm for monitoring ELB 4XX errors
     */
    const http4xxElbAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-ELB-4XX-${name}`,
      {
        tags: { name: `HTTP-ELB-4XX-${name}` },
        name: `HTTP-ELB-4XX-${name}`,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_ELB_4XX_Count",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of elb 4XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeELB4XX,
      }
    );
  }
}
