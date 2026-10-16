import test from 'node:test';
import assert from 'node:assert/strict';
import {canShopPiece,canServicePiece,normalizePieceIntent,pieceName,serviceQuery,serviceDestination} from '../public/piece-intent.js';

test('an unlisted custom feature routes by intent, with Arabic request and a safe editable destination',()=>{
 const item={name_en:'Bespoke curved divider',name_ar:'فاصل منحني',category:'other',search_kind:'service',service_query_ar:'شركة نجارة لتفصيل فاصل منحني',service_query_en:'Joinery company for bespoke curved divider'};
 assert.equal(canShopPiece(item),false);assert.equal(canServicePiece(item),true);
 assert.equal(pieceName(item,'ar'),'فاصل منحني');assert.equal(serviceQuery(item,'ar'),item.service_query_ar);
 const url=new URL(serviceDestination(serviceQuery(item,'ar'),'KW'));
 assert.equal(url.origin,'https://findzia.com');assert.equal(url.searchParams.get('q'),item.service_query_ar);assert.equal(url.searchParams.get('country'),'KW');assert.equal(url.searchParams.get('project'),'services');
 assert.equal(url.searchParams.has('submit'),false);
 assert.equal(new URL(serviceDestination('Woodwork','https://evil.test')).searchParams.has('country'),false);
});

test('mixed work supports both routes and older custom or measured items retain useful defaults',()=>{
 const door={search_kind:'both',name_en:'Door'};
 assert.equal(canShopPiece(door),true);assert.equal(canServicePiece(door),true);
 assert.equal(canShopPiece({mode:'quote'}),false);assert.equal(canServicePiece({mode:'measure'}),true);
 assert.equal(canServicePiece({mode:'ready',name_en:'Sofa'}),false);
 assert.equal(serviceQuery({name_en:'Door',name_ar:'باب'},'ar'),'تنفيذ وتركيب: باب');
 const normalized=normalizePieceIntent({search_kind:'unknown',service_query_en:' x '.repeat(200),surface:'fake'});
 assert.equal(normalized.service_query_en.length,180);assert.equal(normalized.surface,'object');
});
