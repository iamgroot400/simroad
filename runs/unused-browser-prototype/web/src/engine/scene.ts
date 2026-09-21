import {type Scene, type Control} from './types';
export function control(nodeId:string,type:Control['type']='uncontrolled',roads:string[]=[]):Control {
 return {nodeId,type,phases:roads.map(id=>({greenRoadIds:[id],durationSec:8})),currentPhaseIndex:0,elapsedInPhase:0,pedestrianRemaining:0};
}
export function demo():Scene {return {version:1,name:'Little crossroads',spawnRate:42,
 nodes:[{id:'west',x:-240,y:0,type:'endpoint'},{id:'center',x:0,y:0,type:'junction'},{id:'east',x:240,y:0,type:'endpoint'},{id:'north',x:0,y:-210,type:'endpoint'},{id:'south',x:0,y:210,type:'endpoint'}],
 roads:[{id:'west-road',fromNodeId:'west',toNodeId:'center',lanes:2,speedLimit:40,width:3.4,twoWay:true},{id:'east-road',fromNodeId:'center',toNodeId:'east',lanes:2,speedLimit:40,width:3.4,twoWay:true},{id:'north-road',fromNodeId:'north',toNodeId:'center',lanes:1,speedLimit:30,width:3.4,twoWay:true},{id:'south-road',fromNodeId:'center',toNodeId:'south',lanes:1,speedLimit:30,width:3.4,twoWay:true}],
 controls:[{...control('center','signal'),phases:[{greenRoadIds:['west-road','east-road'],durationSec:10},{greenRoadIds:['north-road','south-road'],durationSec:8}]}],
 zones:[{id:'offices',type:'office',x:120,y:-110,radius:75},{id:'homes',type:'residential',x:-120,y:105,radius:75},{id:'school',type:'school',x:-120,y:-105,radius:70},{id:'shops',type:'market',x:120,y:110,radius:75}]};}
export function parseScene(text:string):Scene {
 if(text.length>2_000_000)throw Error('Choose a JSON file smaller than 2 MB.');
 const s=JSON.parse(text) as Scene;
 const finite=(v:unknown,min:number,max:number)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
 if(s?.version!==1||typeof s.name!=='string'||s.name.length>100||!Array.isArray(s.nodes)||!Array.isArray(s.roads)||!Array.isArray(s.controls)||!Array.isArray(s.zones)||s.nodes.length>500||s.roads.length>800||s.zones.length>200||!finite(s.spawnRate,0,120))throw Error('Not a supported Simroad Live city.');
 for(const group of [s.nodes,s.roads,s.zones]){if(group.some(x=>typeof x.id!=='string'||x.id.length>100)||new Set(group.map(x=>x.id)).size!==group.length)throw Error('City objects need unique IDs.');}
 for(const n of s.nodes)if(!finite(n.x,-100000,100000)||!finite(n.y,-100000,100000)||!['junction','endpoint'].includes(n.type))throw Error('Invalid node.');
 for(const r of s.roads){const a=s.nodes.find(n=>n.id===r.fromNodeId),b=s.nodes.find(n=>n.id===r.toNodeId);if(!a||!b||Math.hypot(a.x-b.x,a.y-b.y)<12||!Number.isInteger(r.lanes)||!finite(r.lanes,1,4)||!finite(r.speedLimit,10,100)||!finite(r.width,2.5,5)||typeof r.twoWay!=='boolean')throw Error('Roads need valid endpoints, 1–4 lanes and at least 12 m of length.');}
 if(new Set(s.controls.map(c=>c.nodeId)).size!==s.controls.length||s.controls.length>s.nodes.length)throw Error('Use one control per junction.');
 for(const c of s.controls){if(!s.nodes.some(n=>n.id===c.nodeId)||!['uncontrolled','signal','zebra_crossing','stop_sign'].includes(c.type)||!Array.isArray(c.phases)||c.phases.length>16||(c.type==='signal'&&!c.phases.length))throw Error('Invalid junction control.');for(const p of c.phases)if(!finite(p.durationSec,2,120)||!Array.isArray(p.greenRoadIds)||p.greenRoadIds.some(id=>!s.roads.some(r=>r.id===id&&(r.fromNodeId===c.nodeId||r.toNodeId===c.nodeId))))throw Error('Signal phases need connected roads and durations from 2 to 120 seconds.');c.currentPhaseIndex=0;c.elapsedInPhase=0;c.pedestrianRemaining=0;}
 for(const z of s.zones)if(!['office','residential','school','market','park'].includes(z.type)||!finite(z.x,-100000,100000)||!finite(z.y,-100000,100000)||!finite(z.radius,20,200))throw Error('Invalid activity zone.');
 return s;
}
