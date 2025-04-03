// We can get as fancy with the object generation as we want,
// there are plenty of libraries for generating random data

export const generateStamp = ({ provider }: { provider?: string } = {}) => ({
  provider: provider || "Lens",
  stamp: {
    address: "0x85ff01cff157199527528788ec4ea6336615c989",
    provider: provider || "Lens",
    issuer: "did:ethr:0xd6f8d6ca86aa01e551a311d670a0d1bd8577e5fb",
    issuanceDate: new Date().toISOString(),
    expirationDate: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString(),
    proof: { proofValue: "0x" + Math.random().toString(16).slice(2) },
  },
});

export const generateStamps = (count: number) => {
  const providers = generateProviders(count);
  return Array.from({ length: count }, (_, i) => generateStamp({ provider: providers[i] }));
};

const evmProviders = ["ETHScore#50", "ETHScore#75", "ETHScore#90"];
const nonEVMProviders = ["Lens", "Google"];

export const generateEVMProviders = (count: number) => {
  if (count > evmProviders.length) {
    throw new Error("Not enough providers to generate");
  }

  return evmProviders.slice(0, count);
};

const generateProviders = (count: number) => {
  const providers = [...nonEVMProviders, ...evmProviders];

  if (count > providers.length) {
    throw new Error("Not enough providers to generate");
  }

  return providers.slice(0, count);
};

export const generatePassportAddress = () => "0x6bc998029a4a181acb74645e4d74a0e218e80ca9";
