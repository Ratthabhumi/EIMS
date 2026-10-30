// Offline contract only: importing the harness must never launch a browser.
const assert = require('node:assert/strict');
const {runtimeConfig} = require('./verify_secure_dashboard.cjs');
for (const env of [{}, {EIMS_TEST_BROWSER_BASE_URL:'http://localhost:3449'},
 {EIMS_TEST_BROWSER_BASE_URL:'https://user:password@localhost:3449'},
 {EIMS_TEST_BROWSER_BASE_URL:'https://localhost:3449/path'},
 {EIMS_TEST_BROWSER_BASE_URL:'https://localhost:3449',EIMS_TEST_IGNORE_TLS_ERRORS:'1'}]) {
 assert.throws(()=>runtimeConfig(env));
}
assert.deepEqual(runtimeConfig({EIMS_TEST_BROWSER_BASE_URL:'https://localhost:3449/'}), {
 base:'https://localhost:3449',options:{viewport:{width:1400,height:1000},ignoreHTTPSErrors:false}
});
console.log('PASS: 5 invalid runtime configurations rejected; trusted HTTPS required. No browser executed.');
