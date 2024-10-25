from datetime import datetime
from typing import Dict, List, Optional

from ninja import Field, Schema


class Eip712Domain(Schema):
    name: str


class EIP712Types(Schema):
    name: str
    type: str


class ProofDomain(Schema):
    domain: Eip712Domain
    primaryType: str
    types: Dict[str, List[EIP712Types]]


class CredentialSubject(Schema):
    id: str
    context: Dict[str, str] = Field(None, alias="@context")
    hash: Optional[str] = None
    provider: Optional[str] = None
    address: Optional[str] = None
    challenge: Optional[str] = None
    metaPointer: Optional[str] = None


class Proof(Schema):
    context: str = Field(None, alias="@context")
    type: str
    proofPurpose: str
    proofValue: str
    verificationMethod: str
    created: datetime
    eip712Domain: ProofDomain


class VerifiableEip712Credential(Schema):
    context: List[str] = Field(None, alias="@context")
    type: List[str]
    credentialSubject: CredentialSubject
    issuer: str
    issuanceDate: datetime
    expirationDate: datetime
    proof: Proof
