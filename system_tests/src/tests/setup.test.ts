describe('Test Environment', () => {
  it('should define the required environment variables', () => {
    [process.env.SCORER_API_BASE_URL].forEach((envVar) => {
      expect(envVar).toBeDefined();
    });
  });
});
