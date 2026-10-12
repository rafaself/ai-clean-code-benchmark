// External behavioral oracle: never copied into the agent's workspace.
const fs = require('node:fs');
const { PrismaService } = require('subject/prisma/prisma.service');
const { PubSubService } = require('subject/pubsub/pubsub.service');
const { TeamService } = require('subject/team/team.service');
const { TeamCollectionService } = require('subject/team-collection/team-collection.service');
const { TeamCollectionController } = require('subject/team-collection/team-collection.controller');
const { RESTTeamMemberGuard } = require('subject/team/guards/rest-team-member.guard');
const { GqlCollectionTeamMemberGuard } = require('subject/team-collection/guards/gql-collection-team-member.guard');
const { Reflector } = require('@nestjs/core');
const { SortOptions } = require('subject/types/SortOptions');
const errors = require('subject/errors');
let db, pubsub, teams, service, events;
const time = new Date('2026-01-01T00:00:00.000Z');
const right = (result) => { expect(result._tag).toBe('Right'); return result.right; };
const left = (result, error) => expect(result).toEqual({ _tag: 'Left', left: error });
async function collection(id, orderIndex = 1, parentID = null, teamID = 'team-a', title = id, createdOn = time) {
  return db.teamCollection.create({ data: { id, title, orderIndex, parentID, teamID, createdOn, data: { marker: id } } });
}
async function request(id, collectionID, orderIndex = 1, teamID = 'team-a', title = id, payload = {}) {
  return db.teamRequest.create({ data: { id, collectionID, orderIndex, teamID, title, request: { name: title, method: 'GET', ...payload } } });
}
const folder = (name, folders = [], requests = []) => ({ name, folders, requests, data: '{"keep":true}' });
const trace = {};
beforeAll(async () => {
  db = new PrismaService(); await db.onModuleInit();
  pubsub = new PubSubService(); pubsub.onModuleInit();
  const publish = pubsub.publish.bind(pubsub);
  jest.spyOn(pubsub, 'publish').mockImplementation((topic, payload) => { events.push({ topic, payload }); return publish(topic, payload); });
  teams = new TeamService(db, { registerUserDataHandler() {} }, pubsub);
  service = new TeamCollectionService(db, pubsub, teams);
});
beforeEach(async () => {
  events = [];
  await db.team.deleteMany(); await db.user.deleteMany();
  await db.team.createMany({ data: [{ id: 'team-a', name: 'A' }, { id: 'team-b', name: 'B' }] });
});
afterAll(async () => {
  if (process.env.BENCHMARK_OBSERVATIONS) fs.writeFileSync(process.env.BENCHMARK_OBSERVATIONS, JSON.stringify(trace, null, 2) + '\n');
  if (db) await db.onModuleDestroy();
});

describe('RG', () => {
  test('R01 CRUD state, hierarchy and notification contract', async () => {
    const root = right(await service.createCollection('team-a', 'Root', '{"flag":1}', null));
    const child = right(await service.createCollection('team-a', 'Child', null, root.id));
    expect(right(await service.getCollection(child.id)).parentID).toBe(root.id);
    expect(await service.getParentOfCollection(child.id)).toMatchObject({ id: root.id, title: 'Root' });
    expect(await service.getChildrenOfCollection(root.id, null, 10)).toHaveLength(1);
    expect(right(await service.renameCollection(child.id, 'Renamed')).title).toBe('Renamed');
    expect(right(await service.updateTeamCollection(child.id, '{"other":2}', 'Updated'))).toMatchObject({ title: 'Updated', data: '{"other":2}' });
    expect(right(await service.deleteCollection(root.id))).toBe(true);
    expect(await db.teamCollection.count({ where: { teamID: 'team-a' } })).toBe(0);
    expect(events.map(e => e.topic)).toEqual(['team_coll/team-a/coll_added','team_coll/team-a/coll_added','team_coll/team-a/coll_updated','team_coll/team-a/coll_updated','team_coll/team-a/coll_removed']);
    const ids = new Map([[root.id, 'root'], [child.id, 'child']]);
    const normalize = (value) => JSON.parse(JSON.stringify(value, (key, v) => ids.has(v) ? ids.get(v) : v));
    trace.R01 = normalize(events);
  });
  test('R02 valid nested import persists data and root events', async () => {
    const tree = folder('Imported', [folder('Nested', [], [{ name: 'R', method: 'POST', body: { x: 1 } }])]);
    const rows = right(await service.importCollectionsFromJSON(JSON.stringify([tree]), 'team-a', null));
    expect(rows).toHaveLength(1);
    const exported = right(await service.exportCollectionToJSONObject('team-a', rows[0].id));
    expect(exported).toMatchObject({ name: 'Imported', data: '{"keep":true}', folders: [{ name: 'Nested', requests: [{ name: 'R', method: 'POST', body: { x: 1 } }] }] });
    expect(await db.teamRequest.count()).toBe(1);
    expect(events).toHaveLength(1); expect(events[0].topic).toBe('team_coll/team-a/coll_added');
  });
  test('R03 import parent ownership, missing parent and invalid JSON errors', async () => {
    await collection('other', 1, null, 'team-b');
    const valid = JSON.stringify([folder('Valid')]);
    left(await service.importCollectionsFromJSON(valid, 'team-a', 'other'), errors.TEAM_NOT_OWNER);
    left(await service.importCollectionsFromJSON(valid, 'team-a', 'absent'), errors.TEAM_COLL_NOT_FOUND);
    left(await service.importCollectionsFromJSON('{', 'team-a', null), errors.TEAM_COLL_INVALID_JSON);
    left(await service.importCollectionsFromJSON('{}', 'team-a', null), errors.TEAM_COLL_INVALID_JSON);
    expect(events).toHaveLength(0); expect(await db.teamCollection.count()).toBe(1);
  });
  test('R04 failed import rolls back earlier roots and publishes nothing', async () => {
    const valid = folder('Good');
    // Structurally valid; violates PostgreSQL/Prisma data representation at write time.
    const json = JSON.stringify([valid, folder('Bad')]);
    // Inject a database constraint failure without stubbing the service or transaction.
    await db.$executeRawUnsafe('ALTER TABLE "TeamCollection" ADD CONSTRAINT benchmark_reject_bad CHECK (title <> \'Bad\')');
    try {
      left(await service.importCollectionsFromJSON(json, 'team-a', null), errors.TEAM_COLL_CREATION_FAILED);
      expect(await db.teamCollection.count()).toBe(0); expect(events).toHaveLength(0);
    } finally { await db.$executeRawUnsafe('ALTER TABLE "TeamCollection" DROP CONSTRAINT benchmark_reject_bad'); }
  });
  test('R05 move rejects cycles, self and cross-team destinations', async () => {
    await collection('root'); await collection('child', 1, 'root'); await collection('other', 1, null, 'team-b');
    left(await service.moveCollection('root', 'root'), errors.TEAM_COLL_DEST_SAME);
    left(await service.moveCollection('root', 'child'), errors.TEAM_COLL_IS_PARENT_COLL);
    left(await service.moveCollection('root', 'other'), errors.TEAM_COLL_NOT_SAME_TEAM);
    left(await service.moveCollection('root', null), errors.TEAM_COL_ALREADY_ROOT);
    expect(events).toHaveLength(0);
  });
  test('R06 move child to root preserves records and event payload', async () => {
    await collection('root'); await collection('child', 1, 'root');
    right(await service.moveCollection('child', null));
    expect(right(await service.getCollection('child'))).toMatchObject({ parentID: null, teamID: 'team-a', orderIndex: 2 });
    expect(events).toEqual([{ topic: 'team_coll/team-a/coll_moved', payload: { id: 'child', title: 'child', parentID: null, data: '{"marker":"child"}' } }]);
    trace.R06 = { result: await service.getCollectionCount(null, 'team-a'), events };
  });
  test('R07 root deletion and reordering are isolated by team', async () => {
    await collection('a1', 1); await collection('a2', 2); await collection('b1', 1, null, 'team-b'); await collection('b2', 2, null, 'team-b');
    right(await service.deleteCollection('a1'));
    expect(right(await service.getCollection('a2')).orderIndex).toBe(1);
    expect(right(await service.getCollection('b2')).orderIndex).toBe(2);
    right(await service.updateCollectionOrder('b2', 'b1'));
    expect(right(await service.getCollection('b2')).orderIndex).toBe(1);
    expect(right(await service.getCollection('a2')).orderIndex).toBe(1);
    expect(events.map(e => e.topic)).toEqual(['team_coll/team-a/coll_removed','team_coll/team-b/coll_order_updated']);
  });
  test('R08 title sorts retain existing order and scope', async () => {
    await collection('z', 1, null, 'team-a', 'Zulu'); await collection('a', 2, null, 'team-a', 'Alpha'); await collection('outside', 7, null, 'team-b');
    right(await service.sortTeamCollections('team-a', null, SortOptions.TITLE_ASC));
    expect((await db.teamCollection.findMany({ where: { teamID: 'team-a' }, orderBy: { orderIndex: 'asc' } })).map(c => c.title)).toEqual(['Alpha','Zulu']);
    right(await service.sortTeamCollections('team-a', null, SortOptions.TITLE_DESC));
    expect((await db.teamCollection.findMany({ where: { teamID: 'team-a' }, orderBy: { orderIndex: 'asc' } })).map(c => c.title)).toEqual(['Zulu','Alpha']);
    expect(right(await service.getCollection('outside')).orderIndex).toBe(7);
  });
  test('R09 CLI retrieval requires membership and includes requests', async () => {
    await collection('root'); await collection('child', 1, 'root'); await request('req', 'child');
    left(await service.getCollectionForCLI('root', 'outsider'), errors.TEAM_MEMBER_NOT_FOUND);
    await db.teamMember.create({ data: { teamID: 'team-a', userUid: 'member', role: 'VIEWER' } });
    expect(right(await service.getCollectionForCLI('root', 'member')).folders[0].requests[0]).toMatchObject({ id: 'req', collectionID: 'child' });
  });
  test('R10 REST guard authorizes membership and rejects foreign users', async () => {
    await db.teamMember.create({ data: { teamID: 'team-a', userUid: 'member', role: 'VIEWER' } });
    const handler = TeamCollectionController.prototype.searchByTitle;
    const guard = new RESTTeamMemberGuard(new Reflector(), teams);
    const ctx = (uid, teamID) => ({ getHandler: () => handler, switchToHttp: () => ({ getRequest: () => ({ user: { uid }, params: { teamID } }) }) });
    expect(await guard.canActivate(ctx('member','team-a'))).toBe(true);
    await expect(guard.canActivate(ctx('member','team-b'))).rejects.toThrow(errors.TEAM_MEMBER_NOT_FOUND);
  });
  test('R11 GraphQL collection guard checks role and team membership', async () => {
    await collection('root');
    await db.teamMember.createMany({ data: [{ teamID: 'team-a', userUid: 'viewer', role: 'VIEWER' }, { teamID: 'team-a', userUid: 'editor', role: 'EDITOR' }] });
    function mutation() {}
    Reflect.defineMetadata('requiresTeamRole', ['OWNER','EDITOR'], mutation);
    const guard = new GqlCollectionTeamMemberGuard(new Reflector(), teams, service);
    const ctx = (uid) => ({ getArgs: () => [undefined, { collectionID: 'root' }, { req: { user: { uid } } }, {}], getType: () => 'graphql', getHandler: () => mutation, getClass: () => TeamCollectionController });
    expect(await guard.canActivate(ctx('editor'))).toBe(true);
    expect(await guard.canActivate(ctx('viewer'))).toBe(false);
    await expect(guard.canActivate(ctx('outsider'))).rejects.toThrow(errors.TEAM_REQ_NOT_MEMBER);
  });
  test('R12 missing collections and invalid titles/data preserve errors', async () => {
    left(await service.getCollection('absent'), errors.TEAM_COLL_NOT_FOUND);
    left(await service.exportCollectionToJSONObject('team-a','absent'), errors.TEAM_INVALID_COLL_ID);
    left(await service.createCollection('team-a','',null,null), errors.TEAM_COLL_SHORT_TITLE);
    left(await service.createCollection('team-a','Good','',null), errors.TEAM_COLL_DATA_INVALID);
    expect(events).toHaveLength(0);
  });
  test('R13 search preserves literal matching, ancestry, grouping and isolation', async () => {
    await collection('root',1,null,'team-a','Parent'); await collection('child',1,'root','team-a','needle_100%');
    await request('req','child',1,'team-a','needle_100%'); await collection('foreign',1,null,'team-b','needle_100%');
    const rows=right(await service.searchByTitle('_100%', 'team-a', 10, 0)).data;
    expect(rows.map(r => [r.id,r.type])).toEqual([['child','collection'],['req','request']]);
    expect(rows[0].path).toEqual([{ id:'root',title:'Parent',type:'collection',path:[] }]);
    expect(rows[1].path[0].id).toBe('child');
    expect(right(await service.searchByTitle('missing','team-a',10,0)).data).toEqual([]);
    trace.R13=rows;
  });
});

describe('T01', () => {
  test.each(['object','string'])('canonical nested request metadata (%s payload)', async (kind) => {
    await collection('root'); await collection('child',1,'root');
    const payload={ id:'stale',name:'Old',method:'POST',headers:[{key:'x',value:'y'}],body:{value:7} };
    await request('req','child',1,'team-a','Renamed',kind==='string' ? JSON.stringify(payload) : payload);
    // request() spreads objects; write the string form explicitly for this case.
    if(kind==='string') await db.teamRequest.update({where:{id:'req'},data:{request:JSON.stringify(payload)}});
    const exported=right(await service.exportCollectionToJSONObject('team-a','root')).folders[0].requests[0];
    expect(exported).toEqual({...payload,id:'req',name:'Renamed'});
  });
  test('duplication carries canonical nested request names into new rows', async () => {
    await collection('root',1,null,'team-a','Root'); await collection('child',1,'root','team-a','Child');
    await request('req','child',1,'team-a','Renamed',{name:'Old'});
    right(await service.duplicateTeamCollection('root'));
    const duplicate=await db.teamCollection.findFirst({where:{teamID:'team-a',title:'Root - Duplicate'}});
    expect(duplicate).not.toBeNull();
    const nested=await db.teamCollection.findFirst({where:{parentID:duplicate.id}});
    const copied=await db.teamRequest.findFirst({where:{collectionID:nested.id}});
    expect(copied.title).toBe('Renamed'); expect(copied.id).not.toBe('req');
  });
});
describe('T02', () => {
  test('roots follow orderIndex then ID, regardless of insertion order', async () => {
    await collection('z',3); await collection('b',1); await collection('a',1); await collection('m',2); await collection('foreign',0,null,'team-b');
    await collection('child-late',2,'a'); await collection('child-first',1,'a');
    await request('r-late','child-first',2); await request('r-first','child-first',1);
    const rows=JSON.parse(right(await service.exportCollectionsToJSON('team-a')));
    expect(rows.map(c=>c.id)).toEqual(['a','b','m','z']);
    expect(rows[0].folders.map(c=>c.id)).toEqual(['child-first','child-late']);
    expect(rows[0].folders[0].requests.map(r=>r.id)).toEqual(['r-first','r-late']);
    expect(JSON.parse(right(await service.exportCollectionsToJSON('absent')))).toEqual([]);
  });
});
describe('T03', () => {
  const malformed=[null,{name:'X',requests:[]},{name:'X',folders:[],requests:null},{name:'',folders:[],requests:[]},{name:'X',folders:[null],requests:[]},{name:'X',folders:[],requests:[null]},{name:'X',folders:[],requests:[{name:5}]},{name:'X',folders:[],requests:[{name:''}]}];
  test.each(malformed.map((value,index)=>[index,value]))('invalid nested structure %i rejected before transaction', async (index,value) => {
    const transaction=jest.spyOn(db,'$transaction');
    try {
      const result=await service.importCollectionsFromJSON(JSON.stringify([folder('Good'),value]),'team-a',null);
      left(result,errors.TEAM_COLL_INVALID_JSON);
      expect(transaction).not.toHaveBeenCalled();
      expect(await db.teamCollection.count()).toBe(0); expect(events).toHaveLength(0);
    } finally { transaction.mockRestore(); }
  });
  test('empty lists and unnormalized nonempty names remain valid', async () => {
    expect(right(await service.importCollectionsFromJSON('[]','team-a',null))).toEqual([]);
    const rows=right(await service.importCollectionsFromJSON(JSON.stringify([folder(' ')]),'team-a',null));
    expect(rows[0].title).toBe(' ');
  });
  test('malformed structure takes precedence over missing parent', async () => {
    left(await service.importCollectionsFromJSON('[null]','team-a','absent'),errors.TEAM_COLL_INVALID_JSON);
  });
});
describe('T04', () => {
  test.each([null,'parent'])('creation sort preserves sibling and team scope (%s)', async (parentID) => {
    expect(SortOptions.CREATED_ASC).toBe('CREATED_ASC');
    if(parentID) { await collection('parent'); await collection('other-parent',2); await collection('other-child',8,'other-parent'); }
    await collection('late',1,parentID,'team-a','Alpha',new Date('2026-01-03'));
    await collection('b',2,parentID,'team-a','Bravo',time);
    await collection('a',3,parentID,'team-a','Zulu',time);
    await collection('foreign',7,null,'team-b');
    right(await service.sortTeamCollections('team-a',parentID,SortOptions.CREATED_ASC));
    const rows=await db.teamCollection.findMany({where:{teamID:'team-a',parentID},orderBy:{orderIndex:'asc'}});
    expect(rows.map(c=>c.id)).toEqual(['a','b','late']);expect(rows.map(c=>c.orderIndex)).toEqual([1,2,3]);
    expect(right(await service.getCollection('foreign')).orderIndex).toBe(7);
    if(parentID)expect(right(await service.getCollection('other-child')).orderIndex).toBe(8);
    right(await service.sortTeamCollections('absent',null,SortOptions.CREATED_ASC));
  });
});
describe('T05', () => {
  test('descending similarity and ID ties within each paginated result group', async () => {
    await collection('container',1,null,'team-a','Parent');
    for(const [i,id,title] of [[1,'z','alpha'],[2,'a','alpha'],[3,'far','alpha abcdefghijklmnop']]) {
      await collection(id,i,'container','team-a',title); await request('r-'+id,'container',i,'team-a',title);
    }
    await collection('foreign',1,null,'team-b','alpha');
    const titles=await db.$queryRawUnsafe('SELECT id, similarity(title, $1)::float8 AS score FROM "TeamCollection" WHERE "teamID"=$2 AND title ILIKE $3','alpha','team-a','%alpha%');
    const ids=titles.sort((a,b)=>b.score-a.score || a.id.localeCompare(b.id)).map(r=>r.id);
    for(const [take,skip,start] of [[10,0,0],[2,1,0],[2,2,2]]) {
      const rows=right(await service.searchByTitle('alpha','team-a',take,skip)).data;
      const expected=ids.slice(start,start+take);
      expect(rows.filter(r=>r.type==='collection').map(r=>r.id)).toEqual(expected);
      expect(rows.filter(r=>r.type==='request').map(r=>r.id)).toEqual(expected.map(id=>'r-'+id));
      expect(rows.map(r=>r.type)).toEqual([...expected.map(()=>'collection'),...expected.map(()=>'request')]);
      for(const row of rows)expect(row.path[0].id).toBe('container');
    }
  });
});
