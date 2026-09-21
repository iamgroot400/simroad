const {chromium} = require(process.env.PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const browser = await chromium.launch({headless: true, channel: "msedge"});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(process.env.SIMROAD_URL || "http://127.0.0.1:8765");
    await page.waitForFunction(async () => {
      const response = await fetch("/api/state");
      const snapshot = await response.json();
      return ["ready", "finished", "stopped"].includes(snapshot.status);
    });
    const screen = async point => page.evaluate(p => {
      const rectangle = canvas.getBoundingClientRect(), projected = project(p);
      return {x: rectangle.x + projected[0], y: rectangle.y + projected[1]};
    }, point);
    const paint = async (button, points) => {
      await page.getByRole("button", {name: button, exact: true}).click();
      const coordinates = [];
      for (const point of points) coordinates.push(await screen(point));
      await page.mouse.move(coordinates[0].x, coordinates[0].y);
      await page.mouse.down();
      for (const point of coordinates.slice(1)) await page.mouse.move(point.x, point.y, {steps: 5});
      await page.mouse.up();
    };
    const guide = await page.evaluate(() => {
      const [x0, y0, x1, y1] = map.bounds;
      const width = x1 - x0, height = y1 - y0;
      return {
        origin: [[x0 + width * .12, y0 + height * .15], [x0 + width * .12, y0 + height * .85]],
        destination: [[x0 + width * .88, y0 + height * .15], [x0 + width * .88, y0 + height * .85]],
        parking: [[x0 + width * .72, y0 + height * .35], [x0 + width * .72, y0 + height * .65]],
      };
    });
    await paint("Origin brush", guide.origin);
    await paint("Destination brush", guide.destination);
    await paint("Parking brush", guide.parking);
    await page.locator("#spawn-count").fill("80");
    await page.locator("#spawn-spread").fill("40");
    await page.locator("#parking-probability").fill("30");
    await page.locator("#parking-duration").fill("30");
    await page.getByRole("button", {name: "Queue mixed vehicles", exact: true}).click();
    if (!await page.locator("#vehicle-detail").isHidden()) throw Error("Destination visible before selection");
    await page.locator("#seed").fill("19");
    await page.locator("#speed").selectOption("100");
    await page.locator("#start").click();
    await page.waitForFunction(() => state?.spawn?.added === 80 && state.vehicles.length, null, {timeout: 60000});
    await page.locator("#pause").click();
    await page.waitForFunction(() => state.status === "paused");
    const vehicle = await page.evaluate(() => state.vehicles[0]);
    const position = await screen(vehicle.position);
    await page.mouse.click(position.x, position.y);
    await page.waitForFunction(() => !document.getElementById("vehicle-detail").hidden);
    const result = await page.evaluate(() => ({
      types: state.spawn.type_counts,
      parkingStops: state.spawn.parking_stops,
      destination: document.getElementById("vehicle-destination").textContent,
      errors: state.error,
    }));
    await page.screenshot({path: "docs/images/traffic-areas.png", fullPage: true});
    if (errors.length || result.errors || Object.keys(result.types).length !== 3 || !result.destination.includes("Destination edge"))
      throw Error(JSON.stringify({errors, result}));
    console.log(JSON.stringify(result));
    await page.locator("#stop").click();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
