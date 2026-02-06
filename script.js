const canvas = document.querySelector("#game");
const context = canvas.getContext("2d");
const speedValue = document.querySelector("#speed");
const scoreValue = document.querySelector("#score");
const bestValue = document.querySelector("#best");
const startButton = document.querySelector("#start");
const pauseButton = document.querySelector("#pause");
const restartButton = document.querySelector("#restart");

const lanes = [120, 240, 360];
const road = {
  top: 40,
  bottom: canvas.height - 40,
  left: 60,
  right: canvas.width - 60,
};

const player = {
  lane: 1,
  width: 48,
  height: 90,
  y: canvas.height - 140,
  color: "#ff6b6b",
};

const state = {
  running: false,
  paused: false,
  speed: 4,
  score: 0,
  best: 0,
  obstacles: [],
  lastSpawn: 0,
  time: 0,
};

function resetGame() {
  state.speed = 4;
  state.score = 0;
  state.obstacles = [];
  state.lastSpawn = 0;
  state.time = 0;
  player.lane = 1;
  updateHud();
}

function updateHud() {
  speedValue.textContent = `${Math.round(state.speed * 12)} km/h`;
  scoreValue.textContent = Math.floor(state.score).toString();
  bestValue.textContent = Math.floor(state.best).toString();
}

function spawnObstacle() {
  const lane = lanes[Math.floor(Math.random() * lanes.length)];
  const size = 70 + Math.random() * 20;
  state.obstacles.push({
    x: lane,
    y: road.top - size,
    width: 48,
    height: size,
    color: "#6bffb3",
  });
}

function update(delta) {
  if (!state.running || state.paused) {
    return;
  }

  state.time += delta;
  state.score += delta * state.speed * 0.15;
  state.speed = Math.min(10, 4 + state.score / 400);

  if (state.time - state.lastSpawn > 800 - state.speed * 45) {
    spawnObstacle();
    state.lastSpawn = state.time;
  }

  for (const obstacle of state.obstacles) {
    obstacle.y += state.speed * 6;
  }

  state.obstacles = state.obstacles.filter(
    (obstacle) => obstacle.y < canvas.height + obstacle.height
  );

  for (const obstacle of state.obstacles) {
    if (checkCollision(player, obstacle)) {
      state.running = false;
      state.best = Math.max(state.best, state.score);
      updateHud();
    }
  }

  updateHud();
}

function checkCollision(car, obstacle) {
  const carX = lanes[car.lane] - car.width / 2;
  const carY = car.y;

  const overlapX =
    carX < obstacle.x + obstacle.width / 2 &&
    carX + car.width > obstacle.x - obstacle.width / 2;
  const overlapY =
    carY < obstacle.y + obstacle.height &&
    carY + car.height > obstacle.y;

  return overlapX && overlapY;
}

function drawRoad() {
  context.fillStyle = "#0c0e18";
  context.fillRect(0, 0, canvas.width, canvas.height);

  context.fillStyle = "#1c1f2b";
  context.fillRect(road.left, road.top, road.right - road.left, road.bottom - road.top);

  context.strokeStyle = "#f8f8f8";
  context.lineWidth = 6;
  context.setLineDash([]);
  context.beginPath();
  context.moveTo(road.left, road.top);
  context.lineTo(road.left, road.bottom);
  context.moveTo(road.right, road.top);
  context.lineTo(road.right, road.bottom);
  context.stroke();

  context.strokeStyle = "#ffd369";
  context.lineWidth = 4;
  context.setLineDash([24, 18]);
  for (const lane of lanes.slice(0, -1)) {
    const mid = (lane + lanes[lanes.indexOf(lane) + 1]) / 2;
    context.beginPath();
    context.moveTo(mid, road.top + 10);
    context.lineTo(mid, road.bottom - 10);
    context.stroke();
  }
}

function drawCar(car) {
  const x = lanes[car.lane];
  const y = car.y;

  context.fillStyle = car.color;
  context.fillRect(x - car.width / 2, y, car.width, car.height);

  context.fillStyle = "#111";
  context.fillRect(x - car.width / 2 + 6, y + 12, car.width - 12, 24);
  context.fillRect(x - car.width / 2 + 6, y + 48, car.width - 12, 24);

  context.fillStyle = "#ffffff";
  context.fillRect(x - car.width / 2 + 8, y + 72, car.width - 16, 8);
}

function drawObstacle(obstacle) {
  context.fillStyle = obstacle.color;
  context.fillRect(
    obstacle.x - obstacle.width / 2,
    obstacle.y,
    obstacle.width,
    obstacle.height
  );
}

function drawOverlay() {
  if (state.running) {
    return;
  }

  context.fillStyle = "rgba(0, 0, 0, 0.55)";
  context.fillRect(0, 0, canvas.width, canvas.height);

  context.fillStyle = "#fff";
  context.font = "bold 28px sans-serif";
  context.textAlign = "center";
  context.fillText("点击开始，挑战极速", canvas.width / 2, canvas.height / 2 - 10);

  if (state.score > 0) {
    context.font = "16px sans-serif";
    context.fillText(
      `本局得分 ${Math.floor(state.score)} · 最高 ${Math.floor(state.best)}`,
      canvas.width / 2,
      canvas.height / 2 + 20
    );
  }
}

function render() {
  drawRoad();
  drawCar(player);
  state.obstacles.forEach(drawObstacle);
  drawOverlay();
}

let lastFrame = performance.now();
function loop(now) {
  const delta = now - lastFrame;
  lastFrame = now;
  update(delta);
  render();
  requestAnimationFrame(loop);
}

function moveLeft() {
  if (player.lane > 0) {
    player.lane -= 1;
  }
}

function moveRight() {
  if (player.lane < lanes.length - 1) {
    player.lane += 1;
  }
}

function togglePause() {
  if (!state.running) {
    return;
  }
  state.paused = !state.paused;
  pauseButton.textContent = state.paused ? "继续" : "暂停";
}

startButton.addEventListener("click", () => {
  if (!state.running) {
    resetGame();
    state.running = true;
    state.paused = false;
    pauseButton.textContent = "暂停";
  }
});

restartButton.addEventListener("click", () => {
  resetGame();
  state.running = true;
  state.paused = false;
  pauseButton.textContent = "暂停";
});

pauseButton.addEventListener("click", togglePause);

window.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft" || event.key.toLowerCase() === "a") {
    moveLeft();
  }
  if (event.key === "ArrowRight" || event.key.toLowerCase() === "d") {
    moveRight();
  }
  if (event.key === " " || event.key.toLowerCase() === "p") {
    togglePause();
  }
});

canvas.addEventListener("click", () => {
  if (!state.running) {
    resetGame();
    state.running = true;
  }
});

resetGame();
requestAnimationFrame(loop);
