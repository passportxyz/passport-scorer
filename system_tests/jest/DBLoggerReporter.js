const { Pool } = require('pg');

class SystemTestResultWriter {
  constructor(connectionString) {
    this.pool = new Pool({
      connectionString,
      max: 2, // max number of clients in the pool
      idleTimeoutMillis: 30000,
    });
  }

  async writeTestResult(testResult) {
    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      const query = `
                INSERT INTO passport_admin_systemtestresult
                (name, category, success, error, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            `;

      const values = [
        testResult.testName,
        JSON.stringify(testResult.category), // Convert array to JSON
        testResult.status === 'passed', // Convert to boolean
        testResult.error || null, // Handle undefined
        testResult.timestamp,
      ];

      await client.query(query, values);
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async close() {
    await this.pool.end();
  }
}

const TERMINAL_COLOR_CODE_REGEX =
  /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g;

class DBLoggerReporter {
  getWriter() {
    if (!this.writer) {
      this.writer = new SystemTestResultWriter(process.env.DB_CONNECTION_STRING);
    }
    return this.writer;
  }

  async onTestResult(_test, testResult) {
    const writer = this.getWriter();
    const { testResults } = testResult;
    for (const result of testResults) {
      const { title, status, failureMessages, ancestorTitles } = result;
      await writer.writeTestResult({
        category: ancestorTitles,
        testName: title,
        status,
        error: failureMessages.join('\n').replace(TERMINAL_COLOR_CODE_REGEX, '') || null,
        timestamp: new Date(),
      });
    }
  }

  async onRunComplete() {
    if (this.writer) {
      await this.writer.close();
    }
  }
}

module.exports = DBLoggerReporter;
