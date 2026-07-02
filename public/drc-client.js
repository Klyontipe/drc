/**
 * API client-side Team DRC — GitHub Pages, sans serveur.
 * Données en localStorage (stockage partagé à venir sur OVH).
 */
(function () {
  const STORE_KEY = 'drc_data_v1';
  const SESSION_KEY = 'drc_session';
  const RESET_HOUR = 14;
  const VOTE_OPEN_HOUR = 9;
  const APP_NAME = 'Team DRC';

  const PERSONS = ['jade', 'david', 'thibault', 'lorenzo'];
  const NICKNAMES = { jade: 'Radé', david: 'Davee', thibault: 'riz souflée', lorenzo: 'lolo' };
  const PINS = { jade: '4827', david: '6374', thibault: '9153', lorenzo: '2846' };
  const EMAILS = {
    jade: 'forlinijade@gmail.com',
    david: 'david.fanti@free.fr',
    thibault: 'thibault@teamdrc.fr',
    lorenzo: 'fortinilorenzo40@gmail.com',
  };

  const ANCHOR_DATE = new Date(2026, 5, 23);
  const ANCHOR_INDEX = 3;

  const FOODS = [
    { id: 'pancakes', name: 'Pancakes', emoji: '🥞', rare: false, weight: 12 },
    { id: 'crepe', name: 'Crêpes', emoji: '🫓', rare: false, weight: 12 },
    { id: 'gateau', name: 'Gâteau', emoji: '🎂', rare: false, weight: 12 },
    { id: 'cookies', name: 'Cookies', emoji: '🍪', rare: false, weight: 12 },
    { id: 'brownies', name: 'Brownies', emoji: '🍫', rare: false, weight: 12 },
    { id: 'muffins', name: 'Muffins', emoji: '🧁', rare: false, weight: 12 },
    { id: 'cupcake', name: 'Cupcake', emoji: '🧁', rare: false, weight: 12 },
    { id: 'madeleine', name: 'Madeleine', emoji: '🍰', rare: false, weight: 12 },
    { id: 'cheesecake', name: 'Cheesecake', emoji: '🧀', rare: true, weight: 3 },
    { id: 'tiramisu', name: 'Tiramisu', emoji: '☕', rare: true, weight: 3 },
    { id: 'cinnamon_roll', name: 'Cinnamon roll', emoji: '🌀', rare: true, weight: 3 },
  ];

  function avatarPath(file) {
    const base = (window.DRC_CONFIG?.basePath || '').replace(/\/$/, '');
    return base ? `${base}/${file}` : file;
  }

  const DEFAULT_AVATARS = {
    jade: { emoji: '🌸', bg: '#ff6b6b', bg2: '#c92a2a', border: '#ff8787', role: 'Le feu au cul', photo: avatarPath('avatars/jade.png') },
    david: { emoji: '🎯', bg: '#ffe66d', bg2: '#f59f00', border: '#ffd43b', role: 'Le café en IV', photo: avatarPath('avatars/david.png') },
    thibault: { emoji: '⚡', bg: '#4ecdc4', bg2: '#087f5b', border: '#63e6be', role: 'Croustillant garanti', photo: avatarPath('avatars/thibault.png') },
    lorenzo: { emoji: '👑', bg: '#a78bfa', bg2: '#7048e8', border: '#b197fc', role: 'Le boss du tupperware', photo: avatarPath('avatars/lorenzo.png') },
  };

  function nick(id) { return NICKNAMES[id] || id; }

  function loadStore() {
    try {
      return JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    } catch {
      return {};
    }
  }

  function saveStore(data) {
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
  }

  function ensureData() {
    const data = loadStore();
    data.roulette_draws = data.roulette_draws || {};
    data.rating_sessions = data.rating_sessions || {};
    data.food_averages = data.food_averages || {};
    data.notifications = data.notifications || {};
    data.emails = { ...EMAILS, ...data.emails };
    return data;
  }

  function persist(data) {
    saveStore(data);
    return data;
  }

  function getTuesdayIndex(d) {
    const date = new Date(d);
    date.setHours(12, 0, 0, 0);
    const anchor = new Date(ANCHOR_DATE);
    anchor.setHours(12, 0, 0, 0);
    const diffWeeks = Math.round((date - anchor) / (7 * 24 * 60 * 60 * 1000));
    return ((ANCHOR_INDEX + diffWeeks) % PERSONS.length + PERSONS.length) % PERSONS.length;
  }

  function personForTuesday(d) {
    return PERSONS[getTuesdayIndex(d)];
  }

  function getPeriodStart(now = new Date()) {
    const d = new Date(now);
    const today = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const pyWeekday = (today.getDay() + 6) % 7;
    const daysSinceTue = (pyWeekday - 1 + 7) % 7;
    const thisTuesday = new Date(today);
    thisTuesday.setDate(today.getDate() - daysSinceTue);
    const period = new Date(thisTuesday);
    period.setHours(RESET_HOUR, 0, 0, 0);
    if (d >= period) return period;
    const prev = new Date(thisTuesday);
    prev.setDate(prev.getDate() - 7);
    prev.setHours(RESET_HOUR, 0, 0, 0);
    return prev;
  }

  function getNextReset(now = new Date()) {
    const p = getPeriodStart(now);
    return new Date(p.getTime() + 7 * 24 * 60 * 60 * 1000);
  }

  function getTargetTuesday(periodStart) {
    const t = new Date(periodStart);
    t.setDate(t.getDate() + 7);
    return t;
  }

  function periodKey(periodStart) {
    return periodStart.toISOString();
  }

  function isoDate(d) {
    const x = new Date(d);
    return x.toISOString().slice(0, 10);
  }

  function isValidDraw(draw) {
    if (!draw?.target_tuesday) return false;
    const target = new Date(draw.target_tuesday + 'T12:00:00');
    return draw.spun_by === personForTuesday(target);
  }

  function findDrawForTuesday(targetIso) {
    const data = ensureData();
    for (const draw of Object.values(data.roulette_draws)) {
      if (draw.target_tuesday === targetIso && isValidDraw(draw)) return draw;
    }
    return null;
  }

  function weightedFoodPick() {
    const pool = [];
    for (const food of FOODS) {
      for (let i = 0; i < food.weight; i++) pool.push(food);
    }
    const chosen = pool[Math.floor(Math.random() * pool.length)];
    return { id: chosen.id, name: chosen.name, emoji: chosen.emoji, rare: chosen.rare };
  }

  function getSessionUser() {
    return localStorage.getItem(SESSION_KEY);
  }

  function setSessionUser(id) {
    if (id) localStorage.setItem(SESSION_KEY, id);
    else localStorage.removeItem(SESSION_KEY);
  }

  function authenticatePin(pin) {
    for (const pid of PERSONS) {
      if (PINS[pid] === pin) return pid;
    }
    return null;
  }

  async function sendEmail(to, subject, message) {
    const cfg = window.DRC_CONFIG?.emailjs;
    if (!cfg?.publicKey || !cfg?.serviceId || !cfg?.templateId) {
      console.warn('EmailJS non configuré — email non envoyé à', to);
      return { ok: false, error: 'EmailJS non configuré' };
    }
    if (typeof emailjs === 'undefined') {
      return { ok: false, error: 'EmailJS non chargé' };
    }
    try {
      await emailjs.send(cfg.serviceId, cfg.templateId, {
        to_email: to,
        subject,
        message,
        app_url: window.DRC_CONFIG?.appUrl || location.href,
      }, { publicKey: cfg.publicKey });
      return { ok: true };
    } catch (e) {
      console.error('EmailJS error', e);
      return { ok: false, error: String(e) };
    }
  }

  async function notifyAll(subject, message) {
    const data = ensureData();
    const results = [];
    for (const pid of PERSONS) {
      const email = data.emails[pid];
      if (email) results.push(await sendEmail(email, subject, message));
    }
    return results;
  }

  function voteWindowStatus(now = new Date()) {
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (today.getDay() !== 2) {
      return { open: false, reason: 'not_tuesday' };
    }
    const draw = findDrawForTuesday(isoDate(today));
    if (!draw) return { open: false, reason: 'no_draw', food: null };
    const opensAt = new Date(today);
    opensAt.setHours(VOTE_OPEN_HOUR, 0, 0, 0);
    if (now < opensAt) {
      return {
        open: false,
        reason: 'too_early',
        opens_at: opensAt.toISOString(),
        food: draw.food,
        baker: nick(personForTuesday(today)),
      };
    }
    return {
      open: true,
      opens_at: opensAt.toISOString(),
      food: draw.food,
      baker: nick(personForTuesday(today)),
    };
  }

  function finalizeRatingIfReady(data, sessionKey) {
    const session = data.rating_sessions[sessionKey];
    if (!session || session.completed) return session;
    const baker = session.baker_id;
    const votersNeeded = PERSONS.filter(p => p !== baker);
    const votes = session.votes || {};
    if (Object.keys(votes).length < votersNeeded.length) return session;

    const values = votersNeeded.map(v => votes[v]);
    const avg = Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10;
    session.average = avg;
    session.completed = true;
    session.completed_at = new Date().toISOString();

    const fid = session.food.id;
    const stat = data.food_averages[fid] || {
      name: session.food.name,
      emoji: session.food.emoji,
      total: 0,
      sessions: 0,
      average: null,
    };
    stat.total = Math.round((stat.total + avg) * 100) / 100;
    stat.sessions += 1;
    stat.average = Math.round((stat.total / stat.sessions) * 10) / 10;
    data.food_averages[fid] = stat;

    if (!session.results_email_sent) {
      const lines = votersNeeded.map(v => `  · ${nick(v)} : ${votes[v]}/10`).join('\n');
      const subject = `⭐ ${APP_NAME} — ${avg}/10 pour ${session.food.name}`;
      const plain = `Notes du mardi ${session.tuesday}\n\nPlat : ${session.food.emoji} ${session.food.name}\nPar : ${session.baker_name}\nMoyenne : ${avg}/10\n\nDétail :\n${lines}`;
      notifyAll(subject, plain);
      session.results_email_sent = true;
    }
    return session;
  }

  async function checkReminders(data, now = new Date()) {
    const period = getPeriodStart(now);
    const key = periodKey(period);
    const target = getTargetTuesday(period);
    if (data.roulette_draws[key] && isValidDraw(data.roulette_draws[key])) return;
    const reminderKey = `reminder_${key}`;
    if (data.notifications[reminderKey] || now < period) return;
    const name = nick(personForTuesday(target));
    const targetStr = target.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    const subject = `🎰 ${APP_NAME} — C'est l'heure de tirer !`;
    const plain = `C'est l'heure ! ${name} doit tirer la roulette avant le mardi ${targetStr}.\nC'est toi qui ramèneras ce qui sera tiré !`;
    await notifyAll(subject, plain);
    data.notifications[reminderKey] = new Date().toISOString();
    persist(data);
  }

  async function checkVoteOpen(data) {
    const window = voteWindowStatus();
    if (!window.open) return;
    const today = isoDate(new Date());
    const notifyKey = `vote_open_${today}`;
    if (data.notifications[notifyKey]) return;
    const draw = findDrawForTuesday(today);
    if (!draw) return;
    if (!data.rating_sessions[today]) {
      const baker = personForTuesday(new Date());
      data.rating_sessions[today] = {
        tuesday: today,
        baker_id: baker,
        baker_name: nick(baker),
        food: draw.food,
        votes: {},
        average: null,
        completed: false,
        results_email_sent: false,
        created_at: new Date().toISOString(),
      };
    }
    const food = draw.food;
    const baker = nick(personForTuesday(new Date()));
    const tuesdayStr = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    await notifyAll(
      `⭐ ${APP_NAME} — C'est l'heure de noter !`,
      `Les votes sont ouverts pour le plat du mardi ${tuesdayStr}.\n${food.emoji} ${food.name} par ${baker}\nConnecte-toi et note de 1 à 10.`,
    );
    data.notifications[notifyKey] = new Date().toISOString();
    persist(data);
  }

  async function request(path, opts = {}) {
    const method = (opts.method || 'GET').toUpperCase();
    const body = opts.body ? JSON.parse(opts.body) : {};
    let data = ensureData();
    const userId = getSessionUser();

    if (path === '/api/avatars' && method === 'GET') {
      return { ...DEFAULT_AVATARS };
    }

    if (path === '/api/auth/me' && method === 'GET') {
      if (!userId) {
        return { logged_in: false };
      }
      const av = DEFAULT_AVATARS[userId] || {};
      return {
        logged_in: true,
        user_id: userId,
        name: nick(userId),
        nickname: nick(userId),
        user_email: data.emails[userId] || EMAILS[userId],
        photo: av.photo,
        emoji: av.emoji,
      };
    }

    if (path === '/api/auth/login' && method === 'POST') {
      const pin = String(body.pin || '').trim();
      if (!/^\d{4}$/.test(pin)) throw { status: 400, error: 'Code à 4 chiffres' };
      const pid = authenticatePin(pin);
      if (!pid) throw { status: 401, error: 'Code incorrect' };
      setSessionUser(pid);
      return { ok: true, user_id: pid, name: nick(pid), nickname: nick(pid) };
    }

    if (path === '/api/auth/logout' && method === 'POST') {
      setSessionUser(null);
      return { ok: true };
    }

    if (path === '/api/roulette' && method === 'GET') {
      await checkReminders(data);
      data = ensureData();
      const now = new Date();
      const period = getPeriodStart(now);
      const key = periodKey(period);
      const target = getTargetTuesday(period);
      const responsible = personForTuesday(target);
      const raw = data.roulette_draws[key];
      const draw = raw && isValidDraw(raw) ? raw : null;
      return {
        period_start: period.toISOString(),
        next_reset: getNextReset(now).toISOString(),
        target_tuesday: isoDate(target),
        responsible,
        responsible_name: nick(responsible),
        responsible_nickname: nick(responsible),
        draw,
        is_spun: !!draw,
        can_spin: !draw,
        window_open: now >= period,
        logged_in: userId,
        reset_hour: RESET_HOUR,
        all_foods: FOODS,
      };
    }

    if (path === '/api/roulette/spin' && method === 'POST') {
      const status = await request('/api/roulette', { method: 'GET' });
      if (!status.can_spin) throw { status: 403, error: 'Tu ne peux pas tirer maintenant', ...status };
      if (userId !== status.responsible) {
        throw { status: 403, error: `Seul ${status.responsible_name} peut tirer cette semaine` };
      }
      data = ensureData();
      const period = getPeriodStart();
      const key = periodKey(period);
      const target = getTargetTuesday(period);
      const food = weightedFoodPick();
      const draw = {
        period_start: key,
        target_tuesday: isoDate(target),
        food,
        spun_by: userId,
        spun_by_name: nick(userId),
        spun_at: new Date().toISOString(),
      };
      data.roulette_draws[key] = draw;
      persist(data);
      const targetStr = target.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
      const rare = food.rare ? ' ✨ RARE !' : '';
      const plain = `${nick(userId)} a tiré : ${food.emoji} ${food.name}${rare} · À ramener le mardi ${targetStr} !`;
      const emailResults = await notifyAll(`🎰 ${APP_NAME} — ${food.emoji} ${food.name}`, plain);
      return { draw, status: await request('/api/roulette'), email_results: emailResults };
    }

    if (path === '/api/ratings' && method === 'GET') {
      await checkVoteOpen(data);
      data = ensureData();
      const window = voteWindowStatus();
      const foodAverages = data.food_averages;
      if (!window.open) {
        const base = { active: false, food_averages: foodAverages, vote_window: window };
        if (window.reason === 'too_early' && window.food) {
          base.pending = true;
          base.opens_at = window.opens_at;
          base.preview = { food: window.food, baker: window.baker };
        }
        return base;
      }
      const today = isoDate(new Date());
      let session = data.rating_sessions[today];
      if (!session) {
        const draw = findDrawForTuesday(today);
        if (!draw) return { active: false, food_averages: foodAverages, vote_window: window };
        const baker = personForTuesday(new Date());
        session = {
          tuesday: today,
          baker_id: baker,
          baker_name: nick(baker),
          food: draw.food,
          votes: {},
          average: null,
          completed: false,
          results_email_sent: false,
          created_at: new Date().toISOString(),
        };
        data.rating_sessions[today] = session;
        persist(data);
      }
      const baker = session.baker_id;
      const votes = session.votes || {};
      const votersNeeded = PERSONS.filter(p => p !== baker);
      return {
        active: true,
        vote_window: window,
        session: {
          ...session,
          votes_detail: Object.fromEntries(Object.entries(votes).map(([k, v]) => [nick(k), v])),
          voters_needed: votersNeeded.map(nick),
          votes_count: Object.keys(votes).length,
          votes_total: votersNeeded.length,
        },
        can_vote: !!(userId && userId !== baker && !session.completed && !(userId in votes)),
        has_voted: !!(userId && userId in votes),
        is_baker: userId === baker,
        food_averages: foodAverages,
      };
    }

    if (path === '/api/ratings/vote' && method === 'POST') {
      if (!userId) throw { status: 401, error: 'Connecte-toi d\'abord' };
      const score = Number(body.score);
      if (!Number.isInteger(score) || score < 1 || score > 10) {
        throw { status: 400, error: 'Note entre 1 et 10' };
      }
      data = ensureData();
      const today = isoDate(new Date());
      const window = voteWindowStatus();
      if (!window.open) throw { status: 403, error: 'Votes fermés' };
      const session = data.rating_sessions[today];
      if (!session) throw { status: 400, error: 'Pas de session' };
      if (userId === session.baker_id) throw { status: 403, error: 'Le chef ne vote pas' };
      if (session.completed) throw { status: 403, error: 'Votes terminés' };
      if (session.votes[userId] != null) throw { status: 403, error: 'Déjà voté' };
      session.votes[userId] = score;
      finalizeRatingIfReady(data, today);
      persist(data);
      return request('/api/ratings', { method: 'GET' });
    }

    throw { status: 404, error: 'Route inconnue' };
  }

  window.DRCClient = { request };
  // Actif uniquement sur GitHub Pages (pas quand Flask tourne en local)
  if (!location.hostname.endsWith('github.io') && !window.DRC_CONFIG?.staticMode) {
    delete window.DRCClient;
  }
})();
