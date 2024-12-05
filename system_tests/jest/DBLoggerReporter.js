async function writeTestResultToDB(testResult) {
  // TODO
  console.log('Pretend writing test result to DB:', testResult);
}

class DBLoggerReporter {
  async onTestResult(_test, testResult) {
    const { testResults } = testResult;
    for (const result of testResults) {
      const { fullName, status, failureMessages } = result;
      await writeTestResultToDB({
        testName: fullName,
        status,
        error: failureMessages.join('\n') || null,
        timestamp: new Date(),
      });
    }
  }
}

module.exports = DBLoggerReporter;
