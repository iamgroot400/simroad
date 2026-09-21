import type {Scene, Road, Step} from './types';
export function length(scene: Scene, road: Road): number {
 const a=scene.nodes.find(n=>n.id===road.fromNodeId), b=scene.nodes.find(n=>n.id===road.toNodeId);
 return a&&b ? Math.hypot(a.x-b.x,a.y-b.y) : 0;
}
export function shortestPath(scene: Scene, start: string, end: string): Step[] {
 const distance = new Map<string,number>([[start,0]]), previous=new Map<string,{node:string;step:Step}>(), open=new Set(scene.nodes.map(n=>n.id));
 while(open.size){let current:string|undefined, best=Infinity;for(const n of open){const d=distance.get(n)??Infinity;if(d<best){current=n;best=d;}}if(!current||current===end)break;open.delete(current);
 for(const road of scene.roads){const forward=road.fromNodeId===current;const next=forward?road.toNodeId:road.twoWay&&road.toNodeId===current?road.fromNodeId:null;if(!next||!open.has(next))continue;const candidate=best+length(scene,road);if(candidate<(distance.get(next)??Infinity)){distance.set(next,candidate);previous.set(next,{node:current,step:{roadId:road.id,forward}});}}}
 const route:Step[]=[];let cursor=end;while(cursor!==start){const p=previous.get(cursor);if(!p)return [];route.unshift(p.step);cursor=p.node;}return route;
}
