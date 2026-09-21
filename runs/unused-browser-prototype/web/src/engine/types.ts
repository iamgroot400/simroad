export interface Node { id: string; x: number; y: number; type: 'junction' | 'endpoint' }
export interface Road { id: string; fromNodeId: string; toNodeId: string; lanes: number; speedLimit: number; width: number; twoWay: boolean }
export interface Phase { greenRoadIds: string[]; durationSec: number }
export interface Control { nodeId: string; type: 'uncontrolled' | 'signal' | 'zebra_crossing' | 'stop_sign'; phases: Phase[]; currentPhaseIndex: number; elapsedInPhase: number; pedestrianRemaining: number }
export interface Step { roadId: string; forward: boolean }
export interface Vehicle { id: string; roadId: string; laneIndex: number; positionOnRoad: number; speed: number; targetSpeed: number; length: number; type: 'car' | 'bus' | 'motorcycle'; route: Step[]; routeIndex: number; stopWait: number }
export type ZoneType = 'office' | 'residential' | 'school' | 'market' | 'park';
export interface Zone { id: string; x: number; y: number; radius: number; type: ZoneType }
export interface Scene { version: 1; name: string; nodes: Node[]; roads: Road[]; controls: Control[]; zones: Zone[]; spawnRate: number }
export const colors: Record<ZoneType,string> = {office:'#658bd3', residential:'#60a39b',school:'#d6a848',market:'#bd81ac',park:'#89ac6c'};
export const uid = (prefix: string) => prefix + Math.random().toString(36).slice(2, 11);
