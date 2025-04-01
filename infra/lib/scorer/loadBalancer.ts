import * as aws from "@pulumi/aws";
import { Input } from "@pulumi/pulumi";

import { Topic } from "@pulumi/aws/sns";
import { defaultTags } from "../tags";

type AlarmConfiguration = {
  threshold: number;
  datapointsToAlarm: number;
  evaluationPeriods: number;
  period: number;
};

type BurstAndSustainAlarmConfiguration = {
  burst: AlarmConfiguration;
  sustain: AlarmConfiguration;
};

export type TargetGroupAlarmsConfiguration = {
  targetResponseTime: BurstAndSustainAlarmConfiguration;
  percentHTTPCodeTarget4XX: BurstAndSustainAlarmConfiguration;
  percentHTTPCodeTarget5XX: BurstAndSustainAlarmConfiguration;
};

export type AlarmConfigurations = {
  percentHTTPCodeELB4XX: BurstAndSustainAlarmConfiguration;
  percentHTTPCodeELB5XX: BurstAndSustainAlarmConfiguration;
  indexerErrorThreshold: number; // threshold for indexer logged errors
  indexerErrorPeriod: number; // period for reporting indexer logged errors

  default: TargetGroupAlarmsConfiguration;
  "passport-analysis-GET-0": TargetGroupAlarmsConfiguration;
  "cc-v1-score-POST-0": TargetGroupAlarmsConfiguration;
  "cc-v1-st-bulk-PATCH-0": TargetGroupAlarmsConfiguration;
  "submit-passport-0": TargetGroupAlarmsConfiguration;
  "cc-v1-st-bulk-DELETE-0": TargetGroupAlarmsConfiguration;
  "passport-v2-stamp-score": TargetGroupAlarmsConfiguration;
  "passport-v2-model-score": TargetGroupAlarmsConfiguration;
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
    [
      {
        name: `HTTP-ELB-5XX-${name}-burst`,
        ...loadBalancerAlarmThresholds.percentHTTPCodeELB5XX.burst,
      },
      {
        name: `HTTP-ELB-5XX-${name}-sustain`,
        ...loadBalancerAlarmThresholds.percentHTTPCodeELB5XX.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        name,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        evaluationPeriods,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period,
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
              period,
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
        threshold,
      });
    });

    /*
     * Alarm for monitoring ELB 4XX errors
     */
    [
      {
        name: `HTTP-ELB-4XX-${name}-burst`,
        ...loadBalancerAlarmThresholds.percentHTTPCodeELB4XX.burst,
      },
      {
        name: `HTTP-ELB-4XX-${name}-sustain`,
        ...loadBalancerAlarmThresholds.percentHTTPCodeELB4XX.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        name,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        evaluationPeriods,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: albArnSuffix,
              },
              namespace: metricNamespace,
              period,
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
              period,
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
        threshold,
      });
    });
  }
}
