describe('Test Environment', () => {
  it('should define the required environment variables', () => {
    const envVars = [
      'SCORER_API_BASE_URL',
      'ALCHEMY_API_KEY',
      'TEST_API_SCORER_ID',
      'TEST_SCORER_API_KEY',
      'TEST_UI_SCORER_ID',
      'TEST_INTERNAL_API_SECRET',
      'IAM_BASE_URL',
      'NFT_HOLDER_PRIVATE_KEY',
      'DOMAIN',
    ];
    const missingEnvVars = envVars.filter((envVarName) => !process.env[envVarName]);
    expect(missingEnvVars).toEqual([]);
  });
});
