describe('Test Environment', () => {
  it('should define the required environment variables', () => {
    const missingEnvVars = ['SCORER_API_BASE_URL', 'ALCHEMY_API_KEY', 'TEST_UI_SCORER_ID'].filter(
      (envVarName) => !process.env[envVarName]
    );
    expect(missingEnvVars).toEqual([]);
  });
});
