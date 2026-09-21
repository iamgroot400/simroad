// Intelligent Driver Model. Distances in m, speeds in m/s, acceleration in m/s².
// Formula: https://traffic-simulation.de/info/info_IDM.html
export function idm(speed:number, desired:number, gap=Infinity, leaderSpeed=speed):number {
 const acceleration=1.5, comfortableBraking=2, minimumGap=2, headway=1.2;
 const desiredGap=minimumGap+Math.max(0,speed*headway+speed*(speed-leaderSpeed)/(2*Math.sqrt(acceleration*comfortableBraking)));
 return Math.max(-8,acceleration*(1-Math.pow(speed/Math.max(.1,desired),4)-Math.pow(desiredGap/Math.max(.1,gap),2)));
}
