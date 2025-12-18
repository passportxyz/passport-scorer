import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import {
  createListenerRule,
  createWeightedListenerRule,
  getRoutingPercentages,
  pathCondition,
  methodCondition,
  hostCondition,
  createTargetGroupAlarms,
} from "./routing-utils";
import { AlarmConfigurations } from "./loadBalancer";

/**
 * Target groups that need to be provided for routing configuration
 */
export interface TargetGroups {
  // V2 API
  pythonV2StampScore: aws.lb.TargetGroup;
  pythonV2ModelScore: aws.lb.TargetGroup;

  // Rust scorer (serves multiple endpoints)
  rustScorer: aws.lb.TargetGroup;
  rustScorerInternal: aws.lb.TargetGroup;

  // Ceramic Cache / Submit endpoints
  pythonCeramicCacheBulkPost: aws.lb.TargetGroup;
  pythonCeramicCacheBulkPatch: aws.lb.TargetGroup;
  pythonCeramicCacheBulkDelete: aws.lb.TargetGroup;
  pythonCeramicCacheScorePost: aws.lb.TargetGroup;
  pythonCeramicCacheScoreGet: aws.lb.TargetGroup;
  pythonCeramicCacheWeights: aws.lb.TargetGroup;
  pythonCeramicCacheStamp: aws.lb.TargetGroup;
  pythonSubmitPassport: aws.lb.TargetGroup;
  pythonPassportAnalysis: aws.lb.TargetGroup;

  // Registry (generic handler for multiple endpoints)
  pythonRegistry: aws.lb.TargetGroup;

  // Internal endpoints (ECS service on internal ALB)
  pythonInternal?: aws.lb.TargetGroup;

  // Embed endpoints (internal ALB)
  pythonEmbedAddStamps: aws.lb.TargetGroup;
  pythonEmbedValidateKey: aws.lb.TargetGroup;
  pythonEmbedGetScore: aws.lb.TargetGroup;

  // App API
  pythonAppApiNonce: aws.lb.TargetGroup;
  pythonAppApiAuthenticate: aws.lb.TargetGroup;
}

/**
 * Configure all ALB routing rules in one centralized location
 * This is the single source of truth for all routing decisions
 */
export function configureAllRouting(args: {
  publicListener: aws.lb.Listener | pulumi.Output<aws.lb.Listener>;
  internalListener?: aws.lb.Listener | pulumi.Output<aws.lb.Listener>;
  targetGroups: TargetGroups;
  stack: string;
  envName: string;
  alb?: aws.lb.LoadBalancer;
  alertTopic?: aws.sns.Topic;
  alarmConfigurations?: AlarmConfigurations;
}): void {
  const { publicListener, internalListener, targetGroups, stack, envName, alb, alertTopic, alarmConfigurations } = args;
  const routingPercentages = getRoutingPercentages(stack);

  // Extract listener ARNs (handle both direct Listener and Output<Listener>)
  const publicListenerArn = pulumi.output(publicListener).apply((l) => l.arn);
  const internalListenerArn = internalListener ? pulumi.output(internalListener).apply((l) => l.arn) : undefined;

  // =============================================================
  // V2 API ENDPOINTS (Priority 2000, 2110-2112, 2200)
  // NOTE: These must be ordered correctly:
  //   - 2000: Block *.gitcoin.co (evaluated first)
  //   - 2110-2112: Specific endpoints (evaluated next)
  //   - 2200: Catch-all for *.passport.xyz (evaluated last)
  // =============================================================

  // Priority 2000: Block V2 API on *.gitcoin.co domain
  createListenerRule({
    name: `v2-block-gitcoin-${envName}`,
    listenerArn: publicListenerArn,
    priority: 2000,
    conditions: [pathCondition("/v2/*"), hostCondition("*.gitcoin.co")],
    fixedResponse: {
      contentType: "application/json",
      messageBody: JSON.stringify({
        msg: "This service is not available for requests to the `*.gitcoin.co` domain",
      }),
      statusCode: "400",
    },
  });

  // Priority 2110: /v2/models/score/{address} - Python only (*.passport.xyz)
  createListenerRule({
    name: `v2-models-score-${envName}`,
    listenerArn: publicListenerArn,
    priority: 2110,
    targetGroupArn: targetGroups.pythonV2ModelScore.arn,
    conditions: [pathCondition("/v2/models/score/*"), methodCondition("GET"), hostCondition("*.passport.xyz")],
  });

  // Priority 2111: /v2/stamps/*/score/*/history - Python only (*.passport.xyz)
  // NOTE: This must come before 2112 since it's more specific
  createListenerRule({
    name: `v2-stamps-score-history-${envName}`,
    listenerArn: publicListenerArn,
    priority: 2111,
    targetGroupArn: targetGroups.pythonRegistry.arn,
    conditions: [
      pathCondition("/v2/stamps/*/score/*/history"),
      methodCondition("GET"),
      hostCondition("*.passport.xyz"),
    ],
  });

  // Priority 2112: /v2/stamps/{scorer_id}/score/{address} - DUAL IMPLEMENTATION (*.passport.xyz)
  createWeightedListenerRule({
    name: `v2-stamps-score-${envName}`,
    listenerArn: publicListenerArn,
    priority: 2112,
    targetGroups: [
      { arn: targetGroups.pythonV2StampScore.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/v2/stamps/*/score/*"), methodCondition("GET"), hostCondition("*.passport.xyz")],
  });

  // Priority 2200: V2 API catch-all for *.passport.xyz
  // NOTE: This catches any other /v2/* requests from passport.xyz domain
  createListenerRule({
    name: `v2-catchall-${envName}`,
    listenerArn: publicListenerArn,
    priority: 2200,
    targetGroupArn: targetGroups.pythonRegistry.arn,
    conditions: [pathCondition("/v2/*"), hostCondition("*.passport.xyz")],
  });

  // =============================================================
  // CERAMIC CACHE & SUBMIT ENDPOINTS (Priority 1030-1039)
  // NOTE: Changed from 1011-1020 to avoid conflict with old listener rules at 1001-1015
  // =============================================================

  // Priority 1030: /registry/submit-passport - Python only
  createListenerRule({
    name: `submit-passport-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1030,
    targetGroupArn: targetGroups.pythonSubmitPassport.arn,
    conditions: [pathCondition("/registry/submit-passport"), methodCondition("POST")],
  });

  // Priority 1031: /ceramic-cache/score/* POST - Python only (Rust doesn't implement POST)
  createListenerRule({
    name: `ceramic-cache-score-post-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1031,
    targetGroupArn: targetGroups.pythonCeramicCacheScorePost.arn,
    conditions: [pathCondition("/ceramic-cache/score/*"), methodCondition("POST")],
  });

  // Priority 1032: /ceramic-cache/stamps/bulk POST - DUAL IMPLEMENTATION
  createWeightedListenerRule({
    name: `ceramic-cache-bulk-post-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1032,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheBulkPost.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/stamps/bulk"), methodCondition("POST")],
  });

  // Priority 1033: /ceramic-cache/stamps/bulk PATCH - DUAL IMPLEMENTATION
  createWeightedListenerRule({
    name: `ceramic-cache-bulk-patch-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1033,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheBulkPatch.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/stamps/bulk"), methodCondition("PATCH")],
  });

  // Priority 1034: /ceramic-cache/stamps/bulk DELETE - DUAL IMPLEMENTATION
  createWeightedListenerRule({
    name: `ceramic-cache-bulk-delete-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1034,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheBulkDelete.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/stamps/bulk"), methodCondition("DELETE")],
  });

  // Priority 1035: /passport/analysis/{address} - Python only
  createListenerRule({
    name: `passport-analysis-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1035,
    targetGroupArn: targetGroups.pythonPassportAnalysis.arn,
    conditions: [pathCondition("/passport/analysis/*"), methodCondition("GET")],
  });

  // Priority 1036: /ceramic-cache/score/0x* GET - DUAL IMPLEMENTATION
  // NOTE: The 0x* pattern ensures we only match Ethereum addresses, not other paths
  createWeightedListenerRule({
    name: `ceramic-cache-score-get-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1036,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheScoreGet.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/score/0x*"), methodCondition("GET")],
  });

  // Priority 1037: /ceramic-cache/weights GET - DUAL IMPLEMENTATION
  createWeightedListenerRule({
    name: `ceramic-cache-weights-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1037,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheWeights.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/weights"), methodCondition("GET")],
  });

  // Priority 1038: /ceramic-cache/stamp GET - DUAL IMPLEMENTATION
  createWeightedListenerRule({
    name: `ceramic-cache-stamp-${envName}`,
    listenerArn: publicListenerArn,
    priority: 1038,
    targetGroups: [
      { arn: targetGroups.pythonCeramicCacheStamp.arn, weight: routingPercentages.python },
      { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
    ],
    conditions: [pathCondition("/ceramic-cache/stamp"), methodCondition("GET")],
  });

  // =============================================================
  // INTERNAL ALB - EMBED ENDPOINTS (Priority 2104-2106)
  // NOTE: Changed from 2100-2103 to avoid conflict with old listener rules
  // =============================================================

  if (internalListenerArn) {
    // Priority 2104: /internal/embed/stamps/* POST - DUAL IMPLEMENTATION
    createWeightedListenerRule({
      name: `embed-add-stamps-${envName}`,
      listenerArn: internalListenerArn,
      priority: 2104,
      targetGroups: [
        { arn: targetGroups.pythonEmbedAddStamps.arn, weight: routingPercentages.python },
        { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
      ],
      conditions: [pathCondition("/internal/embed/stamps/*"), methodCondition("POST")],
    });

    // Priority 2105: /internal/embed/validate-api-key GET - DUAL IMPLEMENTATION
    createWeightedListenerRule({
      name: `embed-validate-key-${envName}`,
      listenerArn: internalListenerArn,
      priority: 2105,
      targetGroups: [
        { arn: targetGroups.pythonEmbedValidateKey.arn, weight: routingPercentages.python },
        { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
      ],
      conditions: [pathCondition("/internal/embed/validate-api-key"), methodCondition("GET")],
    });

    // Priority 2106: /internal/embed/score/*/* GET - DUAL IMPLEMENTATION
    createWeightedListenerRule({
      name: `embed-get-score-${envName}`,
      listenerArn: internalListenerArn,
      priority: 2106,
      targetGroups: [
        { arn: targetGroups.pythonEmbedGetScore.arn, weight: routingPercentages.python },
        { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
      ],
      conditions: [pathCondition("/internal/embed/score/*/*"), methodCondition("GET")],
    });

    // Priority 2120: /internal/* CATCH-ALL - DUAL IMPLEMENTATION
    // This catches all other internal endpoints not explicitly routed above
    // Includes: /internal/score/v2/*, /internal/check-bans, /internal/check-revocations,
    // /internal/allow-list/*, /internal/customization/*, /internal/stake/*,
    // /internal/cgrants/*, /internal/embed/weights, etc.
    // NOTE: This takes precedence over the ECS service rule at priority 2202
    const pythonInternalTargetGroup = targetGroups.pythonInternal || targetGroups.pythonRegistry;
    createWeightedListenerRule({
      name: `internal-catch-all-${envName}`,
      listenerArn: internalListenerArn,
      priority: 2120,
      targetGroups: [
        { arn: pythonInternalTargetGroup.arn, weight: routingPercentages.python },
        { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
      ],
      conditions: [pathCondition("/internal/*")],
    });
  }

  // =============================================================
  // APP API ENDPOINTS (Priority 5000-5001)
  // NOTE: Changed from 3000-3001 to avoid conflict with old registry rule at 3000
  // =============================================================

  // Priority 5000: /account/nonce - Python only
  createListenerRule({
    name: `app-api-nonce-${envName}`,
    listenerArn: publicListenerArn,
    priority: 5000,
    targetGroupArn: targetGroups.pythonAppApiNonce.arn,
    conditions: [pathCondition("/account/nonce"), methodCondition("GET", "OPTIONS")],
  });

  // Priority 5001: /ceramic-cache/authenticate* - handles both v1 and v2 (routes internally by path)
  createListenerRule({
    name: `app-api-authenticate-${envName}`,
    listenerArn: publicListenerArn,
    priority: 5001,
    targetGroupArn: targetGroups.pythonAppApiAuthenticate.arn,
    conditions: [pathCondition("/ceramic-cache/authenticate*"), methodCondition("POST", "OPTIONS")],
  });

  // =============================================================
  // CREATE CLOUDWATCH ALARMS FOR ALL TARGET GROUPS
  // =============================================================

  if (alb && alertTopic && alarmConfigurations) {
    // V2 API alarms
    if (targetGroups.pythonV2StampScore) {
      createTargetGroupAlarms({
        name: "passport-v2-stamp-score",
        targetGroup: targetGroups.pythonV2StampScore,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonV2ModelScore) {
      createTargetGroupAlarms({
        name: "passport-v2-model-score",
        targetGroup: targetGroups.pythonV2ModelScore,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }

    // Ceramic Cache alarms
    if (targetGroups.pythonSubmitPassport) {
      createTargetGroupAlarms({
        name: "submit-passport-0",
        targetGroup: targetGroups.pythonSubmitPassport,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheBulkPost) {
      createTargetGroupAlarms({
        name: "cc-v1-st-bulk-POST-0",
        targetGroup: targetGroups.pythonCeramicCacheBulkPost,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheBulkPatch) {
      createTargetGroupAlarms({
        name: "cc-v1-st-bulk-PATCH-0",
        targetGroup: targetGroups.pythonCeramicCacheBulkPatch,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheBulkDelete) {
      createTargetGroupAlarms({
        name: "cc-v1-st-bulk-DELETE-0",
        targetGroup: targetGroups.pythonCeramicCacheBulkDelete,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheScorePost) {
      createTargetGroupAlarms({
        name: "cc-v1-score-POST-0",
        targetGroup: targetGroups.pythonCeramicCacheScorePost,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheScoreGet) {
      createTargetGroupAlarms({
        name: "cc-v1-score-GET-0",
        targetGroup: targetGroups.pythonCeramicCacheScoreGet,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheWeights) {
      createTargetGroupAlarms({
        name: "cc-weights-GET-0",
        targetGroup: targetGroups.pythonCeramicCacheWeights,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonCeramicCacheStamp) {
      createTargetGroupAlarms({
        name: "cc-v1-st-GET-0",
        targetGroup: targetGroups.pythonCeramicCacheStamp,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonPassportAnalysis) {
      createTargetGroupAlarms({
        name: "passport-analysis-GET-0",
        targetGroup: targetGroups.pythonPassportAnalysis,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }

    // Embed alarms (note: embed lambdas don't have alarm configs in the old code, but we'll create them with defaults)
    if (targetGroups.pythonEmbedAddStamps) {
      createTargetGroupAlarms({
        name: "embed-st-lambda",
        targetGroup: targetGroups.pythonEmbedAddStamps,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonEmbedValidateKey) {
      createTargetGroupAlarms({
        name: "embed-rl-lambda",
        targetGroup: targetGroups.pythonEmbedValidateKey,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonEmbedGetScore) {
      createTargetGroupAlarms({
        name: "embed-gs-lambda",
        targetGroup: targetGroups.pythonEmbedGetScore,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }

    // App API alarms
    if (targetGroups.pythonAppApiNonce) {
      createTargetGroupAlarms({
        name: "cc-nonce-lambda",
        targetGroup: targetGroups.pythonAppApiNonce,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
    if (targetGroups.pythonAppApiAuthenticate) {
      createTargetGroupAlarms({
        name: "cc-auth-lambda",
        targetGroup: targetGroups.pythonAppApiAuthenticate,
        alb,
        alertTopic,
        alarmConfigurations,
      });
    }
  }
}
