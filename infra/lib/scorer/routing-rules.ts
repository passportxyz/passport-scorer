import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import {
  createListenerRule,
  createWeightedListenerRule,
  getRoutingPercentages,
  isRustEnabled,
  pathCondition,
  methodCondition,
  hostCondition,
} from "./routing-utils";

/**
 * Target groups that need to be provided for routing configuration
 */
export interface TargetGroups {
  // V2 API
  pythonV2StampScore?: aws.lb.TargetGroup;
  pythonV2ModelScore?: aws.lb.TargetGroup;

  // Rust scorer (serves multiple endpoints)
  rustScorer?: aws.lb.TargetGroup;
  rustScorerInternal?: aws.lb.TargetGroup;

  // Ceramic Cache / Submit endpoints
  pythonCeramicCacheBulkPost?: aws.lb.TargetGroup;
  pythonCeramicCacheBulkPatch?: aws.lb.TargetGroup;
  pythonCeramicCacheBulkDelete?: aws.lb.TargetGroup;
  pythonCeramicCacheScorePost?: aws.lb.TargetGroup;
  pythonCeramicCacheScoreGet?: aws.lb.TargetGroup;
  pythonCeramicCacheWeights?: aws.lb.TargetGroup;
  pythonCeramicCacheStamp?: aws.lb.TargetGroup;
  pythonSubmitPassport?: aws.lb.TargetGroup;
  pythonPassportAnalysis?: aws.lb.TargetGroup;

  // Registry (generic handler for multiple endpoints)
  pythonRegistry?: aws.lb.TargetGroup;

  // Embed endpoints (internal ALB)
  pythonEmbedAddStamps?: aws.lb.TargetGroup;
  pythonEmbedValidateKey?: aws.lb.TargetGroup;
  pythonEmbedGetScore?: aws.lb.TargetGroup;

  // App API
  pythonAppApiNonce?: aws.lb.TargetGroup;
  pythonAppApiAuthenticate?: aws.lb.TargetGroup;
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
}): void {
  const { publicListener, internalListener, targetGroups, stack, envName } = args;
  const routingPercentages = getRoutingPercentages(stack);
  const rustEnabled = isRustEnabled(stack);

  // Extract listener ARNs (handle both direct Listener and Output<Listener>)
  const publicListenerArn = pulumi.output(publicListener).apply(l => l.arn);
  const internalListenerArn = internalListener
    ? pulumi.output(internalListener).apply(l => l.arn)
    : undefined;

  // =============================================================
  // V2 API ENDPOINTS (Priority 2021-2023)
  // =============================================================

  // Priority 2021: /v2/models/score/{address} - Python only
  if (targetGroups.pythonV2ModelScore) {
    createListenerRule({
      name: `v2-models-score-${envName}`,
      listenerArn: publicListenerArn,
      priority: 2021,
      targetGroupArn: targetGroups.pythonV2ModelScore.arn,
      conditions: [
        pathCondition("/v2/models/score/*"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 2023: /v2/stamps/{scorer_id}/score/{address} - DUAL IMPLEMENTATION
  if (targetGroups.pythonV2StampScore && targetGroups.rustScorer) {
    if (rustEnabled) {
      createWeightedListenerRule({
        name: `v2-stamps-score-${envName}`,
        listenerArn: publicListenerArn,
        priority: 2023,
        targetGroups: [
          { arn: targetGroups.pythonV2StampScore.arn, weight: routingPercentages.python },
          { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
        ],
        conditions: [
          pathCondition("/v2/stamps/*/score/*"),
          methodCondition("GET"),
        ],
      });
    } else {
      createListenerRule({
        name: `v2-stamps-score-${envName}`,
        listenerArn: publicListenerArn,
        priority: 2023,
        targetGroupArn: targetGroups.pythonV2StampScore.arn,
        conditions: [
          pathCondition("/v2/stamps/*/score/*"),
          methodCondition("GET"),
        ],
      });
    }
  }

  // =============================================================
  // CERAMIC CACHE & SUBMIT ENDPOINTS (Priority 1000-1010)
  // =============================================================

  // Priority 1000: /submit-passport - Python only
  if (targetGroups.pythonSubmitPassport) {
    createListenerRule({
      name: `submit-passport-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1000,
      targetGroupArn: targetGroups.pythonSubmitPassport.arn,
      conditions: [
        pathCondition("/submit-passport"),
        methodCondition("POST"),
      ],
    });
  }

  // Priority 1001: /ceramic-cache/score/* POST - Python only (not implemented in Rust yet)
  if (targetGroups.pythonCeramicCacheScorePost) {
    createListenerRule({
      name: `ceramic-cache-score-post-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1001,
      targetGroupArn: targetGroups.pythonCeramicCacheScorePost.arn,
      conditions: [
        pathCondition("/ceramic-cache/score/*"),
        methodCondition("POST"),
      ],
    });
  }

  // Priority 1002: /ceramic-cache/stamps/bulk POST - DUAL IMPLEMENTATION
  if (targetGroups.pythonCeramicCacheBulkPost) {
    if (rustEnabled && targetGroups.rustScorer) {
      createWeightedListenerRule({
        name: `ceramic-cache-bulk-post-${envName}`,
        listenerArn: publicListenerArn,
        priority: 1002,
        targetGroups: [
          { arn: targetGroups.pythonCeramicCacheBulkPost.arn, weight: routingPercentages.python },
          { arn: targetGroups.rustScorer.arn, weight: routingPercentages.rust },
        ],
        conditions: [
          pathCondition("/ceramic-cache/stamps/bulk"),
          methodCondition("POST"),
        ],
      });
    } else {
      createListenerRule({
        name: `ceramic-cache-bulk-post-${envName}`,
        listenerArn: publicListenerArn,
        priority: 1002,
        targetGroupArn: targetGroups.pythonCeramicCacheBulkPost.arn,
        conditions: [
          pathCondition("/ceramic-cache/stamps/bulk"),
          methodCondition("POST"),
        ],
      });
    }
  }

  // Priority 1003: /ceramic-cache/stamps/bulk PATCH - Python only
  if (targetGroups.pythonCeramicCacheBulkPatch) {
    createListenerRule({
      name: `ceramic-cache-bulk-patch-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1003,
      targetGroupArn: targetGroups.pythonCeramicCacheBulkPatch.arn,
      conditions: [
        pathCondition("/ceramic-cache/stamps/bulk"),
        methodCondition("PATCH"),
      ],
    });
  }

  // Priority 1004: /ceramic-cache/stamps/bulk DELETE - Python only
  if (targetGroups.pythonCeramicCacheBulkDelete) {
    createListenerRule({
      name: `ceramic-cache-bulk-delete-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1004,
      targetGroupArn: targetGroups.pythonCeramicCacheBulkDelete.arn,
      conditions: [
        pathCondition("/ceramic-cache/stamps/bulk"),
        methodCondition("DELETE"),
      ],
    });
  }

  // Priority 1005: /passport/analysis/{address} - Python only
  if (targetGroups.pythonPassportAnalysis) {
    createListenerRule({
      name: `passport-analysis-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1005,
      targetGroupArn: targetGroups.pythonPassportAnalysis.arn,
      conditions: [
        pathCondition("/passport/analysis/*"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1006: /ceramic-cache/score/* GET - DUAL IMPLEMENTATION (when Rust implements it)
  if (targetGroups.pythonCeramicCacheScoreGet) {
    // For now, Python only - update when Rust implements ceramic cache endpoints
    createListenerRule({
      name: `ceramic-cache-score-get-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1006,
      targetGroupArn: targetGroups.pythonCeramicCacheScoreGet.arn,
      conditions: [
        pathCondition("/ceramic-cache/score/*"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1007: /ceramic-cache/weights GET - Python only (v1 API)
  if (targetGroups.pythonCeramicCacheWeights) {
    createListenerRule({
      name: `ceramic-cache-weights-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1007,
      targetGroupArn: targetGroups.pythonCeramicCacheWeights.arn,
      conditions: [
        pathCondition("/ceramic-cache/weights"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1008: /ceramic-cache/stamp GET - Python only (v1 API)
  if (targetGroups.pythonCeramicCacheStamp) {
    createListenerRule({
      name: `ceramic-cache-stamp-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1008,
      targetGroupArn: targetGroups.pythonCeramicCacheStamp.arn,
      conditions: [
        pathCondition("/ceramic-cache/stamp"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1010: Generic registry fallback - Python only
  if (targetGroups.pythonRegistry) {
    createListenerRule({
      name: `registry-fallback-${envName}`,
      listenerArn: publicListenerArn,
      priority: 1010,
      targetGroupArn: targetGroups.pythonRegistry.arn,
      conditions: [
        pathCondition("/*"),
      ],
    });
  }

  // =============================================================
  // INTERNAL ALB - EMBED ENDPOINTS (Priority 2100-2103)
  // =============================================================

  if (internalListenerArn) {
    // Priority 2100: /internal/embed/stamps/* POST - DUAL IMPLEMENTATION
    if (targetGroups.pythonEmbedAddStamps && targetGroups.rustScorerInternal) {
      if (rustEnabled) {
        createWeightedListenerRule({
          name: `embed-add-stamps-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2100,
          targetGroups: [
            { arn: targetGroups.pythonEmbedAddStamps.arn, weight: routingPercentages.python },
            { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
          ],
          conditions: [
            pathCondition("/internal/embed/stamps/*"),
            methodCondition("POST"),
          ],
        });
      } else {
        createListenerRule({
          name: `embed-add-stamps-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2100,
          targetGroupArn: targetGroups.pythonEmbedAddStamps.arn,
          conditions: [
            pathCondition("/internal/embed/stamps/*"),
            methodCondition("POST"),
          ],
        });
      }
    }

    // Priority 2101: /internal/embed/validate-api-key GET - DUAL IMPLEMENTATION
    if (targetGroups.pythonEmbedValidateKey && targetGroups.rustScorerInternal) {
      if (rustEnabled) {
        createWeightedListenerRule({
          name: `embed-validate-key-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2101,
          targetGroups: [
            { arn: targetGroups.pythonEmbedValidateKey.arn, weight: routingPercentages.python },
            { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
          ],
          conditions: [
            pathCondition("/internal/embed/validate-api-key"),
            methodCondition("GET"),
          ],
        });
      } else {
        createListenerRule({
          name: `embed-validate-key-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2101,
          targetGroupArn: targetGroups.pythonEmbedValidateKey.arn,
          conditions: [
            pathCondition("/internal/embed/validate-api-key"),
            methodCondition("GET"),
          ],
        });
      }
    }

    // Priority 2103: /internal/embed/score/*/* GET - DUAL IMPLEMENTATION
    if (targetGroups.pythonEmbedGetScore && targetGroups.rustScorerInternal) {
      if (rustEnabled) {
        createWeightedListenerRule({
          name: `embed-get-score-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2103,
          targetGroups: [
            { arn: targetGroups.pythonEmbedGetScore.arn, weight: routingPercentages.python },
            { arn: targetGroups.rustScorerInternal.arn, weight: routingPercentages.rust },
          ],
          conditions: [
            pathCondition("/internal/embed/score/*/*"),
            methodCondition("GET"),
          ],
        });
      } else {
        createListenerRule({
          name: `embed-get-score-${envName}`,
          listenerArn: internalListenerArn,
          priority: 2103,
          targetGroupArn: targetGroups.pythonEmbedGetScore.arn,
          conditions: [
            pathCondition("/internal/embed/score/*/*"),
            methodCondition("GET"),
          ],
        });
      }
    }
  }

  // =============================================================
  // APP API ENDPOINTS (Priority 3000-3001)
  // =============================================================

  // Priority 3000: /account/nonce - Python only
  if (targetGroups.pythonAppApiNonce) {
    createListenerRule({
      name: `app-api-nonce-${envName}`,
      listenerArn: publicListenerArn,
      priority: 3000,
      targetGroupArn: targetGroups.pythonAppApiNonce.arn,
      conditions: [
        pathCondition("/account/nonce"),
        methodCondition("GET", "OPTIONS"),
      ],
    });
  }

  // Priority 3001: /ceramic-cache/authenticate - Python only
  if (targetGroups.pythonAppApiAuthenticate) {
    createListenerRule({
      name: `app-api-authenticate-${envName}`,
      listenerArn: publicListenerArn,
      priority: 3001,
      targetGroupArn: targetGroups.pythonAppApiAuthenticate.arn,
      conditions: [
        pathCondition("/ceramic-cache/authenticate"),
        methodCondition("POST", "OPTIONS"),
      ],
    });
  }
}