// Display routes on the mapped road centre lines. No changes to dispatch policy.
const EPS = 1e-7
const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1])
const cross = (a, b) => a[0] * b[1] - a[1] * b[0]
function projection(p, a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1]
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (dx * dx + dz * dz || 1)))
  const point = [a[0] + dx * t, a[1] + dz * t]
  return { point, t, distance: distance(p, point) }
}

export function createRoadNetwork(roads, project, buildingFootprints = []) {
  const obstacles = buildingFootprints.map(ring => {
    const p = ring.map(q => project(...q))
    return { p, minX: Math.min(...p.map(q => q[0])), maxX: Math.max(...p.map(q => q[0])), minZ: Math.min(...p.map(q => q[1])), maxZ: Math.max(...p.map(q => q[1])) }
  })
  const inside = (p, ring) => {
    let result = false
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i], b = ring[j]
      if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) result = !result
    }
    return result
  }
  const blocked = (a, b) => obstacles.some(o => {
    if (Math.max(a[0], b[0]) < o.minX || Math.min(a[0], b[0]) > o.maxX || Math.max(a[1], b[1]) < o.minZ || Math.min(a[1], b[1]) > o.maxZ) return false
    const cuts = [0, 1], u = [b[0] - a[0], b[1] - a[1]]
    for (let i = 0; i < o.p.length; i++) {
      const c = o.p[i], d = o.p[(i + 1) % o.p.length], v = [d[0] - c[0], d[1] - c[1]], w = [c[0] - a[0], c[1] - a[1]], den = cross(u, v)
      if (Math.abs(den) < EPS) continue
      const t = cross(w, v) / den, s = cross(w, u) / den
      if (t > 0 && t < 1 && s >= 0 && s <= 1) cuts.push(t)
    }
    cuts.sort((a, b) => a - b)
    return cuts.slice(1).some((t, i) => {
      if (t - cuts[i] < EPS) return false
      const mid = (t + cuts[i]) / 2
      return inside([a[0] + u[0] * mid, a[1] + u[1] * mid], o.p)
    })
  })
  const segments = []
  // The source only provides widths; omit the 1.2 m pedestrian paths.
  roads.filter(r => r.w >= 2.6).forEach(r => {
    for (let i = 1; i < r.p.length; i++) {
      const a = project(...r.p[i - 1]), b = project(...r.p[i])
      if (distance(a, b) > .1 && !blocked(a, b)) segments.push({ a, b, cuts: [0, 1] })
    }
  })
  for (let i = 0; i < segments.length; i++) for (let j = i + 1; j < segments.length; j++) {
    const a = segments[i], b = segments[j]
    const u = [a.b[0] - a.a[0], a.b[1] - a.a[1]]
    const v = [b.b[0] - b.a[0], b.b[1] - b.a[1]]
    const w = [b.a[0] - a.a[0], b.a[1] - a.a[1]], den = cross(u, v)
    if (Math.abs(den) > EPS) {
      const t = cross(w, v) / den, s = cross(w, u) / den
      if (t >= 0 && t <= 1 && s >= 0 && s <= 1) { a.cuts.push(t); b.cuts.push(s) }
    }
    // Join surveyed T junctions with coordinate rounding gaps of at most 0.6 m.
    for (const p of [a.a, a.b]) { const q = projection(p, b.a, b.b); if (q.distance <= .6) b.cuts.push(q.t) }
    for (const p of [b.a, b.b]) { const q = projection(p, a.a, a.b); if (q.distance <= .6) a.cuts.push(q.t) }
  }
  const nodes = [], edges = [], cells = new Map(), links = []
  function node(p) {
    const x = Math.floor(p[0]), z = Math.floor(p[1])
    for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
      for (const id of cells.get(`${x + dx},${z + dz}`) || []) if (distance(nodes[id], p) <= .6) return id
    }
    const id = nodes.length, key = `${x},${z}`
    nodes.push(p); edges.push([]); cells.set(key, [...(cells.get(key) || []), id]); return id
  }
  segments.forEach(s => {
    const cuts = [...new Set(s.cuts)].sort((a, b) => a - b)
    for (let i = 1; i < cuts.length; i++) {
      const at = t => [s.a[0] + (s.b[0] - s.a[0]) * t, s.a[1] + (s.b[1] - s.a[1]) * t]
      const a = node(at(cuts[i - 1])), b = node(at(cuts[i]))
      if (a === b) continue
      const length = distance(nodes[a], nodes[b])
      edges[a].push({ to: b, length }); edges[b].push({ to: a, length }); links.push({ a, b, length })
    }
  })
  function nearest(p) {
    let best = null
    links.forEach(link => {
      const q = projection(p, nodes[link.a], nodes[link.b])
      if (!best || q.distance < best.distance) best = { ...q, ...link }
    })
    return best
  }
  function route(from, to) {
    const start = nearest(from), end = nearest(to)
    if (!start || !end) return null
    const n = nodes.length, dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1), done = new Uint8Array(n)
    dist[start.a] = distance(start.point, nodes[start.a]); dist[start.b] = distance(start.point, nodes[start.b])
    for (let iter = 0; iter < n; iter++) {
      let u = -1
      for (let i = 0; i < n; i++) if (!done[i] && (u < 0 || dist[i] < dist[u])) u = i
      if (u < 0 || !Number.isFinite(dist[u])) break
      done[u] = 1
      for (const e of edges[u]) if (dist[u] + e.length < dist[e.to]) { dist[e.to] = dist[u] + e.length; prev[e.to] = u }
    }
    const costA = dist[end.a] + distance(nodes[end.a], end.point), costB = dist[end.b] + distance(nodes[end.b], end.point)
    let target = costA <= costB ? end.a : end.b, length = Math.min(costA, costB), path = []
    if (start.a === end.a && start.b === end.b && distance(start.point, end.point) <= length) {
      path = [start.point, end.point]
    } else {
      if (!Number.isFinite(length)) return null
      for (let u = target; u !== -1; u = prev[u]) path.push(nodes[u])
      path = [start.point, ...path.reverse(), end.point]
    }
    path = path.filter((p, i) => i === 0 || distance(p, path[i - 1]) > .01)
    length = path.slice(1).reduce((sum, p, i) => sum + distance(path[i], p), 0)
    return { points: path, length, accessFrom: start.distance, accessTo: end.distance }
  }
  return { route, nearest, nodes, links }
}

// Constant-distance sampling preserves road corners (no spline overshoot).
export function sampleRoadRoute(points, travelled) {
  if (!points.length) return null
  for (let i = 1; i < points.length; i++) {
    const length = distance(points[i - 1], points[i])
    if (travelled <= length || i === points.length - 1) {
      const t = Math.max(0, Math.min(1, travelled / (length || 1)))
      return { x: points[i - 1][0] + (points[i][0] - points[i - 1][0]) * t, z: points[i - 1][1] + (points[i][1] - points[i - 1][1]) * t, angle: Math.atan2(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]) }
    }
    travelled -= length
  }
  return { x: points[0][0], z: points[0][1], angle: 0 }
}
