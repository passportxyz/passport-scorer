async function writeTestResultToDB(testResult) {
  // TODO
  console.log('Pretend writing test result to DB:', testResult);
}

class DBLoggerReporter {
  async onTestResult(_test, testResult) {
    const { testResults } = testResult;
    for (const result of testResults) {
      const { title, status, failureMessages, ancestorTitles } = result;
      await writeTestResultToDB({
        category: ancestorTitles,
        testName: title,
        status,
        error: failureMessages.join('\n') || null,
        timestamp: new Date(),
      });
    }
  }
}

module.exports = DBLoggerReporter;
