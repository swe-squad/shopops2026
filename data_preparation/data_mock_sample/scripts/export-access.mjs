import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

export async function exportAccess(db, root, output) {
  const query = async (sql, params = []) => (await db.query(sql, params)).rows;
  const tables = {};
  for (const table of ['users', 'merchants', 'merchant_memberships', 'user_shop_access']) {
    tables[`access.${table}`] = await query(`SELECT * FROM access.${table} ORDER BY 1,2`);
  }
  const sql = 'SELECT * FROM access.user_shop_access WHERE user_id=$1 ORDER BY shop_key';
  const examples = [];
  for (const userId of [...tables['access.users'].map(row => row.user_id), 'unknown-user', null]) {
    const shops = await query(sql, [userId]);
    examples.push({ user_id: userId, shops });
  }
  assert.deepEqual(examples.map(row => row.shops.length), [4, 2, 2, 0, 0, 0, 0, 0]);
  const grants = tables['access.user_shop_access'];
  assert.equal(grants.length, 8);
  const documentOwners = await query(`SELECT count(*)::int AS invalid FROM raw.documents d
    LEFT JOIN core.shops s ON s.platform=d.platform AND s.source_shop_id=d.shop_id
    WHERE s.shop_key IS NULL OR s.merchant_id<>d.merchant_id`);
  assert.equal(documentOwners[0].invalid, 0);
  await writeFile(new URL('access/user-shop-access.jsonl', root),
    grants.map(row => JSON.stringify(row)).join('\n')+'\n');
  await writeFile(new URL('access.json', output), JSON.stringify({
    policy: 'Active users with active merchant memberships may read all shops of active merchants.',
    trust_boundary: 'Bind user_id from the verified backend session; this export is admin/demo data, not a public response.',
    query: sql, ...tables, examples,
  }, null, 2)+'\n');
  return tables;
}
