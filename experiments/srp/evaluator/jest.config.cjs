const path = require('node:path');
const subject = process.env.BENCHMARK_SUBJECT;
if (!subject || !path.isAbsolute(subject)) throw new Error('Set absolute BENCHMARK_SUBJECT to the backend directory');
const resolve = (name) => require.resolve(name, { paths: [subject] });
module.exports = {
  rootDir: __dirname,
  testMatch: ['<rootDir>/maintenance.spec.cjs'],
  testEnvironment: 'node',
  testTimeout: 30000,
  maxWorkers: 1,
  modulePaths: [path.join(subject, 'node_modules')],
  moduleNameMapper: { '^subject/(.*)$': path.join(subject, 'src/$1'), '^src/(.*)$': path.join(subject, 'src/$1') },
  transform: { '^.+\\.ts$': [resolve('ts-jest'), { tsconfig: path.join(subject, 'tsconfig.json'), diagnostics: false }] },
  collectCoverage: false,
};
