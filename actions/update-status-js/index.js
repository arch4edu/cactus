#!/usr/bin/env node

const yaml = require('js-yaml');
const mysql = require('mysql2/promise');

const PKGBASE_REGEX = /^[a-zA-Z0-9_\/-]+$/;
const STATUS_MAP = {
  built: { status: 'BUILT', detail: '' },
  building: { status: 'BUILDING', detail: null },
  failed: { status: 'FAILED', detail: 'Build failed.' }
};

async function main() {
  const pkgbase = (process.env.INPUT_PKGBASE || '').trim();
  const status = (process.env.INPUT_STATUS || 'failed').trim().toLowerCase();
  const workflow = (process.env.INPUT_WORKFLOW || '').trim();

  if (!pkgbase || !workflow) {
    console.error('❌ Missing required inputs');
    process.exit(1);
  }
  if (!PKGBASE_REGEX.test(pkgbase)) {
    console.error(`❌ Invalid pkgbase: ${pkgbase}`);
    process.exit(1);
  }

  const configYaml = process.env.INPUT_CONFIG?.trim() || process.env.CACTUS_CONFIG;
  if (!configYaml) {
    console.error('❌ CACTUS_CONFIG missing');
    process.exit(1);
  }

  let config;
  try {
    config = yaml.load(configYaml);
  } catch (err) {
    console.error(`❌ Config error: ${err.message}`);
    process.exit(1);
  }

  const db = config.database;
  if (!db) {
    console.error('❌ Missing database config');
    process.exit(1);
  }

  const { status: dbStatus, detail: dbDetail } = STATUS_MAP[status] || STATUS_MAP.failed;
  console.log(`✅ ${pkgbase} → ${dbStatus}`);

  const connection = await mysql.createConnection({
    host: db.HOST,
    port: db.PORT || 3306,
    user: db.USER,
    password: db.PASSWORD,
    database: db.NAME
  });

  try {
    await connection.beginTransaction();

    const [r1] = await connection.execute(
      `INSERT INTO Status (key, status, detail, workflow, timestamp)
       VALUES (?, ?, ?, ?, NOW())
       ON DUPLICATE KEY UPDATE status = VALUES(status), detail = VALUES(detail), workflow = VALUES(workflow), timestamp = NOW()`,
      [pkgbase, dbStatus, dbDetail || '', workflow]
    );
    console.log(`📝 Status: ${r1.affectedRows} rows`);

    if (status === 'built') {
      const [r2] = await connection.execute(
        'UPDATE Version SET oldver = newver WHERE key LIKE ?',
        [pkgbase + '%']
      );
      console.log(`🔄 Version: ${r2.affectedRows} rows`);
    }

    await connection.commit();
  } catch (err) {
    await connection.rollback();
    console.error(`❌ ${err.message}`);
    process.exit(1);
  } finally {
    await connection.end();
  }
}

main().catch(err => {
  console.error(`❌ ${err.message}`);
  process.exit(1);
});
