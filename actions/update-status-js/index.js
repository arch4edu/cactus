#!/usr/bin/env node

const yaml = require('js-yaml');
const mysql = require('mysql2/promise');

const PKGBASE_REGEX = /^[a-zA-Z0-9_\/.+-]+$/;
const STATUS_MAP = {
  built: { status: 'BUILT', detail: '' },
  building: { status: 'BUILDING', detail: null },
  failed: { status: 'FAILED', detail: 'Build failed.' },
  stale: { status: 'STALE', detail: '' }
};

async function main() {
  const pkgbaseInput = (process.env.INPUT_PKGBASE || '').trim();
  const status = (process.env.INPUT_STATUS || 'failed').trim().toLowerCase();
  const workflow = (process.env.INPUT_WORKFLOW || '').trim();
  const detailInput = process.env.INPUT_DETAIL?.trim();

  if (!pkgbaseInput || !workflow) {
    console.error('❌ Missing required inputs');
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

  const { status: dbStatus, detail: defaultDetail } = STATUS_MAP[status] || STATUS_MAP.failed;
  // Use provided detail if present, otherwise use default from STATUS_MAP
  const detail = detailInput !== undefined ? detailInput : defaultDetail;

  const pkgbases = pkgbaseInput.split(/\s+/);
  for (const pkgbase of pkgbases) {
    if (!PKGBASE_REGEX.test(pkgbase)) {
      console.error(`❌ Invalid pkgbase: ${pkgbase}`);
      process.exit(1);
    }
  }

  const connection = await mysql.createConnection({
    host: db.HOST,
    port: db.PORT || 3306,
    user: db.USER,
    password: db.PASSWORD,
    database: db.NAME
  });

  try {
    await connection.beginTransaction();

    const detailValue = detail === null ? null : String(detail || '');
    const success = [];
    const failed = [];

    for (const pkgbase of pkgbases) {
      try {
        const [r1] = await connection.execute(
          `INSERT INTO cactus_status (\`key\`, status, detail, workflow, timestamp)
           VALUES (?, ?, ?, ?, NOW())
           ON DUPLICATE KEY UPDATE status = VALUES(status), detail = VALUES(detail), workflow = VALUES(workflow), timestamp = NOW()`,
          [pkgbase, dbStatus, detailValue, workflow]
        );
        console.log(`✅ ${pkgbase} → ${dbStatus}`);
        success.push(pkgbase);
      } catch (err) {
        console.error(`❌ ${pkgbase}: ${err.message}`);
        failed.push(pkgbase);
      }
    }

    if (status === 'built') {
      for (const pkgbase of pkgbases) {
        const [r2] = await connection.execute(
          'UPDATE cactus_version SET oldver = newver WHERE \`key\` LIKE ?',
          [pkgbase + '%']
        );
        console.log(`🔄 ${pkgbase}: ${r2.affectedRows} rows`);
      }
    }

    await connection.commit();
    console.log(`📝 Updated: ${success.length}, Failed: ${failed.length}`);
    if (failed.length > 0) {
      process.exit(1);
    }
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