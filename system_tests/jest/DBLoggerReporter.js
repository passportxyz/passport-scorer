async function writeTestResultToDB(testResult) {
  // TODO
  console.log('Pretend writing test result to DB:', testResult.testName);
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
        error:
          failureMessages.join('\n').replace(
            // Strip terminal color codes
            /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
            ''
          ) || null,
        timestamp: new Date(),
      });
    }
  }
}

module.exports = DBLoggerReporter;
