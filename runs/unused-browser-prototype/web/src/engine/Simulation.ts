import {type Scene,type Vehicle,type Road,type Node,uid} from './types';
import {length,shortestPath} from './graph';
import {idm} from './idm';
import {control} from './scene';

/** Mutable world, independent of React, canvas and browser APIs. tick() uses seconds. */
export class Simulation {
 vehicles:Vehicle[]=[]; time=0; completed=0; private spawnCredit=0; private occupied=new Map<string,number>();
 constructor(public scene:Scene){}
 road(id:string){return this.scene.roads.find(r=>r.id===id);}
 node(id:string){return this.scene.nodes.find(n=>n.id===id);}
 get stats(){return {count:this.vehicles.length,average:this.vehicles.length?this.vehicles.reduce((a,v)=>a+v.speed,0)/this.vehicles.length*3.6:0,stopped:this.vehicles.filter(v=>v.speed<.5).length,completed:this.completed};}
 setControl(nodeId:string,type:ReturnType<typeof control>['type']){let c=this.scene.controls.find(c=>c.nodeId===nodeId);const roads=this.scene.roads.filter(r=>r.fromNodeId===nodeId||r.toNodeId===nodeId).map(r=>r.id);if(!c){c=control(nodeId,type,roads);this.scene.controls.push(c);}else{c.type=type;if(!c.phases.length)c.phases=roads.map(id=>({greenRoadIds:[id],durationSec:8}));c.currentPhaseIndex=0;c.elapsedInPhase=0;c.pedestrianRemaining=0;}return c;}
 requestPedestrian(nodeId:string){const c=this.scene.controls.find(c=>c.nodeId===nodeId);if(c?.type==='zebra_crossing')c.pedestrianRemaining=5;}
 addNode(x:number,y:number):Node{const nearby=this.scene.nodes.find(n=>Math.hypot(n.x-x,n.y-y)<12);if(nearby)return nearby;const n:Node={id:uid('n'),x,y,type:'endpoint'};this.scene.nodes.push(n);return n;}
 addRoad(a:Node,b:Node):Road|undefined{if(a.id===b.id||Math.hypot(a.x-b.x,a.y-b.y)<12||this.scene.roads.some(r=>r.fromNodeId===a.id&&r.toNodeId===b.id||r.twoWay&&r.fromNodeId===b.id&&r.toNodeId===a.id))return;
 const r:Road={id:uid('r'),fromNodeId:a.id,toNodeId:b.id,lanes:1,speedLimit:40,width:3.4,twoWay:true};this.scene.roads.push(r);this.reconcile();return r;}
 removeRoad(id:string){this.scene.roads=this.scene.roads.filter(r=>r.id!==id);this.reconcile();}
 removeNode(id:string){this.scene.roads=this.scene.roads.filter(r=>r.fromNodeId!==id&&r.toNodeId!==id);this.scene.nodes=this.scene.nodes.filter(n=>n.id!==id);this.scene.controls=this.scene.controls.filter(c=>c.nodeId!==id);this.reconcile();}
 moveNode(id:string,x:number,y:number){const n=this.node(id);if(!n)return;const attached=this.scene.roads.filter(r=>r.fromNodeId===id||r.toNodeId===id);if(attached.some(r=>{const other=this.node(r.fromNodeId===id?r.toNodeId:r.fromNodeId)!;return Math.hypot(other.x-x,other.y-y)<12;}))return;
 const previous=new Map(attached.map(r=>[r.id,length(this.scene,r)]));n.x=x;n.y=y;for(const v of this.vehicles){const old=previous.get(v.roadId),r=this.road(v.roadId);if(old&&r)v.positionOnRoad*=length(this.scene,r)/old;}this.reconcile();}
 reconcile(){for(const n of this.scene.nodes)n.type=this.scene.roads.filter(r=>r.fromNodeId===n.id||r.toNodeId===n.id).length>1?'junction':'endpoint';
 for(const c of this.scene.controls){c.phases=c.phases.map(p=>({...p,greenRoadIds:p.greenRoadIds.filter(id=>this.scene.roads.some(r=>r.id===id&&(r.fromNodeId===c.nodeId||r.toNodeId===c.nodeId)))}));c.currentPhaseIndex%=Math.max(1,c.phases.length);}
 // A topology edit may invalidate a whole route. Removing that traveler is intentional.
 this.vehicles=this.vehicles.filter(v=>v.route.slice(v.routeIndex).every(s=>{const r=this.road(s.roadId);return r&&(s.forward||r.twoWay);}));
 for(const v of this.vehicles){const r=this.road(v.roadId)!;v.laneIndex=Math.min(v.laneIndex,r.lanes-1);v.positionOnRoad=Math.min(v.positionOnRoad,length(this.scene,r));}
 // Merge removed lanes without leaving overlapping vehicles.
 const groups=new Map<string,Vehicle[]>();for(const v of this.vehicles){const key=v.roadId+v.route[v.routeIndex].forward+v.laneIndex;groups.set(key,[...(groups.get(key)||[]),v]);}for(const group of groups.values()){group.sort((a,b)=>b.positionOnRoad-a.positionOnRoad);for(let i=1;i<group.length;i++)group[i].positionOnRoad=Math.min(group[i].positionOnRoad,group[i-1].positionOnRoad-group[i-1].length-2);}this.vehicles=this.vehicles.filter(v=>v.positionOnRoad>=0);}
 spawn(){if(this.vehicles.length>=500)return;const endpoints=this.scene.nodes.filter(n=>n.type==='endpoint');const candidates=endpoints.length>1?endpoints:this.scene.nodes;if(candidates.length<2)return;
 for(let attempt=0;attempt<8;attempt++){const a=candidates[Math.floor(Math.random()*candidates.length)],b=candidates[Math.floor(Math.random()*candidates.length)];if(a===b)continue;const route=shortestPath(this.scene,a.id,b.id);if(!route.length)continue;const r=this.road(route[0].roadId)!;const lane=Math.floor(Math.random()*r.lanes);if(this.vehicles.some(v=>v.roadId===r.id&&v.route[v.routeIndex].forward===route[0].forward&&v.laneIndex===lane&&v.positionOnRoad<16))continue;const roll=Math.random(),type=roll<.1?'bus':roll<.25?'motorcycle':'car';this.vehicles.push({id:uid('v'),roadId:r.id,laneIndex:lane,positionOnRoad:0,speed:0,targetSpeed:r.speedLimit/3.6,length:type==='bus'?10:type==='motorcycle'?2.2:4.5,type,route,routeIndex:0,stopWait:0});return;}}
 green(nodeId:string,roadId:string){const c=this.scene.controls.find(c=>c.nodeId===nodeId);if(c?.type!=='signal')return true;const p=c.phases[c.currentPhaseIndex];return !!p&&c.elapsedInPhase<p.durationSec&&p.greenRoadIds.includes(roadId);}
 tick(dt:number){if(!Number.isFinite(dt)||dt<=0)return;let remaining=Math.min(dt,1);while(remaining>1e-8){const step=Math.min(.05,remaining);this.step(step);remaining-=step;}}
 private step(dt:number){this.time+=dt;for(const c of this.scene.controls){c.pedestrianRemaining=Math.max(0,c.pedestrianRemaining-dt);if(c.type==='signal'&&c.phases.length){c.elapsedInPhase+=dt;const p=c.phases[c.currentPhaseIndex];if(c.elapsedInPhase>=p.durationSec+1){c.elapsedInPhase-=p.durationSec+1;c.currentPhaseIndex=(c.currentPhaseIndex+1)%c.phases.length;}}}
 if(this.scene.spawnRate>0){this.spawnCredit+=dt*this.scene.spawnRate/60;while(this.spawnCredit>=1){this.spawn();this.spawnCredit--;}}else this.spawnCredit=0;
 const finished=new Set<string>();
 // Frontmost travelers update first, keeping following and receiving-lane gaps safe.
 for(const v of [...this.vehicles].sort((a,b)=>b.positionOnRoad-a.positionOnRoad)){
 const road=this.road(v.roadId);if(!road){finished.add(v.id);continue;}const len=length(this.scene,road),step=v.route[v.routeIndex],end=step.forward?road.toNodeId:road.fromNodeId;const next=v.route[v.routeIndex+1],nextRoad=next&&this.road(next.roadId);const c=this.scene.controls.find(c=>c.nodeId===end);
 let gap=Infinity,leaderSpeed=v.speed;
 for(const leader of this.vehicles){if(leader.id!==v.id&&!finished.has(leader.id)&&leader.roadId===v.roadId&&leader.laneIndex===v.laneIndex&&leader.route[leader.routeIndex].forward===step.forward&&leader.positionOnRoad>v.positionOnRoad){const g=leader.positionOnRoad-leader.length-v.positionOnRoad;if(g<gap){gap=g;leaderSpeed=leader.speed;}}}
 if(c?.type==='stop_sign'&&len-v.positionOnRoad<9&&v.speed<.6)v.stopWait+=dt;
 let blocked=!!next&&(!this.green(end,road.id)||(c?.type==='zebra_crossing'&&c.pedestrianRemaining>0)||(c?.type==='stop_sign'&&v.stopWait<1)||(this.occupied.get(end)??0)>this.time);
 if(nextRoad){const lane=Math.min(v.laneIndex,nextRoad.lanes-1);for(const other of this.vehicles){if(other.roadId===nextRoad.id&&other.route[other.routeIndex].forward===next.forward&&other.laneIndex===lane){const g=len-v.positionOnRoad+other.positionOnRoad-other.length;if(g<gap){gap=g;leaderSpeed=other.speed;}if(other.positionOnRoad-other.length<8)blocked=true;}}}
 if(blocked&&len-v.positionOnRoad-5<gap){gap=len-v.positionOnRoad-5;leaderSpeed=0;}
 v.targetSpeed=road.speedLimit/3.6;const accel=idm(v.speed,v.targetSpeed,gap,leaderSpeed);const newSpeed=Math.max(0,v.speed+accel*dt);const travel=Math.max(0,Math.min((v.speed+newSpeed)*dt/2,gap===Infinity?Infinity:Math.max(0,gap-.5)));v.speed=travel===0?0:newSpeed;v.positionOnRoad+=travel;
 if(v.positionOnRoad>=len){if(!nextRoad){finished.add(v.id);this.completed++;}else{this.occupied.set(end,this.time+1.1);v.positionOnRoad-=len;v.roadId=nextRoad.id;v.routeIndex++;v.laneIndex=Math.min(v.laneIndex,nextRoad.lanes-1);v.stopWait=0;}}
 }
 this.vehicles=this.vehicles.filter(v=>!finished.has(v.id));}
}
