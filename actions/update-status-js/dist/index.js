#!/usr/bin/env node
/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ 505:
/***/ ((module) => {

module.exports = eval("require")("js-yaml");


/***/ }),

/***/ 464:
/***/ ((module) => {

module.exports = eval("require")("mysql2/promise");


/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __nccwpck_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		var threw = true;
/******/ 		try {
/******/ 			__webpack_modules__[moduleId](module, module.exports, __nccwpck_require__);
/******/ 			threw = false;
/******/ 		} finally {
/******/ 			if(threw) delete __webpack_module_cache__[moduleId];
/******/ 		}
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat */
/******/ 	
/******/ 	if (typeof __nccwpck_require__ !== 'undefined') __nccwpck_require__.ab = __dirname + "/";
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};

const yaml = __nccwpck_require__(505);
const mysql = __nccwpck_require__(464);

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

module.exports = __webpack_exports__;
/******/ })()
;