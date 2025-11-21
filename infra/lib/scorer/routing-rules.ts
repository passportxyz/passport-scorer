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
  pythonCeramicCacheScore?: aws.lb.TargetGroup;
  pythonSubmitPassport?: aws.lb.TargetGroup;
  pythonPassportAnalysis?: aws.lb.TargetGroup;

  // Registry (generic handler for multiple endpoints)
  pythonRegistry?: aws.lb.TargetGroup;

  // Embed endpoints (internal ALB)
  pythonEmbedAddStamps?: aws.lb.TargetGroup;
  pythonEmbedValidateKey?: aws.lb.TargetGroup;
  pythonEmbedGetScore?: aws.lb.TargetGroup;

  // App API
  pythonAppApiEnsPrimary?: aws.lb.TargetGroup;
  pythonAppApiGithubPrimary?: aws.lb.TargetGroup;
}

/**
 * Configure all ALB routing rules in one centralized location
 * This is the single source of truth for all routing decisions
 */
export function configureAllRouting(args: {
  publicListener: aws.lb.Listener;
  internalListener?: aws.lb.Listener;
  targetGroups: TargetGroups;
  stack: string;
  envName: string;
}): void {
  const { publicListener, internalListener, targetGroups, stack, envName } = args;
  const routingPercentages = getRoutingPercentages(stack);
  const rustEnabled = isRustEnabled(stack);

  // =============================================================
  // V2 API ENDPOINTS (Priority 2021-2023)
  // =============================================================

  // Priority 2021: /v2/models/score/{address} - Python only
  if (targetGroups.pythonV2ModelScore) {
    createListenerRule({
      name: `v2-models-score-${envName}`,
      listenerArn: publicListener.arn,
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
        listenerArn: publicListener.arn,
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
        listenerArn: publicListener.arn,
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
      listenerArn: publicListener.arn,
      priority: 1000,
      targetGroupArn: targetGroups.pythonSubmitPassport.arn,
      conditions: [
        pathCondition("/submit-passport"),
        methodCondition("POST"),
      ],
    });
  }

  // Priority 1001: /ceramic-cache/score/* POST - Python only (not implemented in Rust yet)
  if (targetGroups.pythonCeramicCacheScore) {
    createListenerRule({
      name: `ceramic-cache-score-post-${envName}`,
      listenerArn: publicListener.arn,
      priority: 1001,
      targetGroupArn: targetGroups.pythonCeramicCacheScore.arn,
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
        listenerArn: publicListener.arn,
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
        listenerArn: publicListener.arn,
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
      listenerArn: publicListener.arn,
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
      listenerArn: publicListener.arn,
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
      listenerArn: publicListener.arn,
      priority: 1005,
      targetGroupArn: targetGroups.pythonPassportAnalysis.arn,
      conditions: [
        pathCondition("/passport/analysis/*"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1006: /ceramic-cache/score/* GET - DUAL IMPLEMENTATION (when Rust implements it)
  if (targetGroups.pythonCeramicCacheScore) {
    // For now, Python only - update when Rust implements ceramic cache endpoints
    createListenerRule({
      name: `ceramic-cache-score-get-${envName}`,
      listenerArn: publicListener.arn,
      priority: 1006,
      targetGroupArn: targetGroups.pythonCeramicCacheScore.arn,
      conditions: [
        pathCondition("/ceramic-cache/score/*"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 1010: Generic registry fallback - Python only
  if (targetGroups.pythonRegistry) {
    createListenerRule({
      name: `registry-fallback-${envName}`,
      listenerArn: publicListener.arn,
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

  if (internalListener) {
    // Priority 2100: /internal/embed/stamps/* POST - DUAL IMPLEMENTATION
    if (targetGroups.pythonEmbedAddStamps && targetGroups.rustScorerInternal) {
      if (rustEnabled) {
        createWeightedListenerRule({
          name: `embed-add-stamps-${envName}`,
          listenerArn: internalListener.arn,
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
          listenerArn: internalListener.arn,
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
          listenerArn: internalListener.arn,
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
          listenerArn: internalListener.arn,
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
          listenerArn: internalListener.arn,
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
          listenerArn: internalListener.arn,
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

  // Priority 3000: /ens/primary_name - Python only
  if (targetGroups.pythonAppApiEnsPrimary) {
    createListenerRule({
      name: `app-api-ens-primary-${envName}`,
      listenerArn: publicListener.arn,
      priority: 3000,
      targetGroupArn: targetGroups.pythonAppApiEnsPrimary.arn,
      conditions: [
        pathCondition("/ens/primary_name"),
        methodCondition("GET"),
      ],
    });
  }

  // Priority 3001: /github/primary_name - Python only
  if (targetGroups.pythonAppApiGithubPrimary) {
    createListenerRule({
      name: `app-api-github-primary-${envName}`,
      listenerArn: publicListener.arn,
      priority: 3001,
      targetGroupArn: targetGroups.pythonAppApiGithubPrimary.arn,
      conditions: [
        pathCondition("/github/primary_name"),
        methodCondition("GET"),
      ],
    });
  }
}