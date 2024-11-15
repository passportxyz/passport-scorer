# Certificiate bundle

## `AmazonRootCA1.pem`

- AWS acm
- shall be used when connecting to proxy (see thes section `RDS Proxy security` https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.howitworks.html#rds-proxy-security )
- was downloaded from: https://www.amazontrust.com/repository/
- for more information see: https://docs.aws.amazon.com/acm/latest/userguide/acm-concepts.html#ACM-root-CAs

## `global-bundle.pem`

- AWS bundle for any commercial AWS Region
- was downloaded from https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html
- shall be used when connecting to RDS directly (no proxy)

## `all.pem`

- is the concatenation of both of the above file
- to be used in either case (when connecting to RDS or Proxy)
