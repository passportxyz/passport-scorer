import * as pulumi from "@pulumi/pulumi";
import * as cloudflare from "@pulumi/cloudflare";

export function createApiDomainRecord(
  stack: pulumi.Input<string>,
  cloudflareZoneId: pulumi.Input<string>,
  albDnsName: pulumi.Input<string>
) {
  const name = "api-passport-xyz-record";


  // api.review.passport.xyz

  const cloudflareApiRecord =
    stack === "production"
      ? new cloudflare.Record(name, {
          name: "api",
          zoneId: cloudflareZoneId,
          type: "CNAME",
          value: albDnsName,
          allowOverwrite: true,
          comment: "Points to LB handling the backend service requests",
        })
      : "";



  return cloudflareApiRecord;
}
