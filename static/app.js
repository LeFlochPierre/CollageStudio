(() => {
  "use strict";
  const isDisplay = document.body.dataset.mode === "display";
  const $ = (id) => document.getElementById(id);
  const stage = $("stage");
  let settings = {interval:5, capacity:22, mix_videos:true, shuffle:true, video_sound:false};
  let media = [], priority = [], used = new Set(), cards = [], timer = null, paused = false, resetting = false;
  let initialized = false, revision = 0, currentlyAdding = false, audioAllowed = false;
  const notice = (message) => { const el = $("savedMessage"); if (el) el.textContent = message; };

  async function request(path, options={}) {
    const res = await fetch(path, {cache:"no-store", ...options});
    if (!res.ok) {
      const problem = await res.json().catch(() => ({}));
      throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${res.status}`);
    }
    return res.json();
  }
  const random = (a,b) => Math.random()*(b-a)+a;
  const shuffle = (list) => {
    const copy = [...list];
    for (let i=copy.length-1;i>0;i--) {const j=Math.floor(Math.random()*(i+1));[copy[i],copy[j]]=[copy[j],copy[i]];}
    return copy;
  };
  function setProgress() {
    const count = cards.length;
    if ($("stageCount")) $("stageCount").textContent = count ? `${count} / ${settings.capacity} MOMENTS` : "";
    if ($("captionCount")) $("captionCount").textContent = `${media.length} items loaded`;
    if ($("libraryCount")) $("libraryCount").textContent = `${media.length} items`;
    if ($("emptyState")) $("emptyState").classList.toggle("hidden",count>0);
  }
  function eligible() {return media.filter(m => settings.mix_videos || m.kind !== "video");}
  function pickNext() {
    const candidates = eligible().filter(m => !used.has(m.id));
    if (!candidates.length) return null;
    if (settings.shuffle) {
      while (priority.length) {
        const id = priority.shift();
        const match = candidates.find(m => m.id === id);
        if (match) return match;
      }
      return candidates[Math.floor(Math.random()*candidates.length)];
    }
    return candidates.slice().sort((a,b)=>a.name.localeCompare(b.name))[0];
  }
  function placeCard(card, index) {
    // card has already been appended to #stage. Its height comes from the
    // photo/video's real aspect ratio, including the white frame.
    // Scale smaller as the collage capacity increases (e.g. 100 items).
    const density = Math.max(0.38, Math.sqrt(22 / Math.max(22, settings.capacity)));
    let w = random(16, 26) * density;
    card.style.width = `${w}%`;
    card.style.height = "auto";

    // Portrait media may be very tall; shrink to keep the full frame visible.
    const stageHeight = Math.max(1, stage.clientHeight);
    let h = 100 * card.offsetHeight / stageHeight;
    if (h > 70) {
      // Leave room for the frame's fixed-size borders when shrinking.
      w *= Math.max(0.15, (70 - 3) / h);
      card.style.width = `${w}%`;
      h = 100 * card.offsetHeight / stageHeight;
    }

    // Candidate coordinates are percentages of the projector canvas.
    let best = {x:2, y:2, penalty:Infinity};
    for (let attempt = 0; attempt < 34; attempt++) {
      const x = random(2, Math.max(2, 98 - w));
      const y = random(2, Math.max(2, 98 - h));
      let overlap = 0;
      for (const existing of cards) {
        const a = existing.coords;
        const intersection = Math.max(0, Math.min(x+w, a.x+a.w)-Math.max(x, a.x))
          * Math.max(0, Math.min(y+h, a.y+a.h)-Math.max(y, a.y));
        overlap += intersection;
      }
      const penalty = overlap + random(0, 18);
      if (penalty < best.penalty) best = {x, y, penalty};
    }
    card.style.left = `${best.x}%`;
    card.style.top = `${best.y}%`;
    card.style.zIndex = String(10 + index);
    card.style.setProperty("--rotation", `${random(-12, 12).toFixed(2)}deg`);
    return {x:best.x, y:best.y, w, h};
  }

  function waitForOriginalDimensions(element, isVideo) {
    // Wait until the browser knows the *real* proportions before making a card.
    // A broken/unsupported media file is skipped instead of being cropped.
    return new Promise((resolve) => {
      const eventName = isVideo ? "loadedmetadata" : "load";
      let done = false;
      let timeout;
      const dimensions = () => isVideo
        ? {width:element.videoWidth, height:element.videoHeight}
        : {width:element.naturalWidth, height:element.naturalHeight};
      const finish = (value) => {
        if (done) return;
        done = true;
        clearTimeout(timeout);
        element.removeEventListener(eventName, onLoad);
        element.removeEventListener("error", onError);
        resolve(value);
      };
      const onLoad = () => {
        const size = dimensions();
        finish(size.width > 0 && size.height > 0 ? size : null);
      };
      const onError = () => finish(null);
      element.addEventListener(eventName, onLoad);
      element.addEventListener("error", onError);
      timeout = setTimeout(onError, 15000);
      const ready = dimensions();
      if (ready.width > 0 && ready.height > 0) onLoad();
    });
  }
  async function addOne() {
    if (paused || resetting || currentlyAdding) return;
    const next = pickNext();
    if (!next) { if (cards.length) scheduleReset(); return; }
    currentlyAdding = true;
    const addRevision = revision;
    try {
      const card = document.createElement("div");
      card.className = "photo-card";
      card.setAttribute("aria-label", next.name);
      const inner = document.createElement("div");
      inner.className = "photo-inner";
      const isVideo = next.kind === "video";
      const element = document.createElement(isVideo ? "video" : "img");
      if (isVideo) {
        element.muted = !(settings.video_sound && audioAllowed);
        element.autoplay = true;
        element.loop = true;
        element.playsInline = true;
        element.preload = "metadata";
        element.addEventListener("canplay", () => element.play().catch(() => {
          element.muted = true;
          element.play().catch(() => {});
        }), {once:true});
        const mark = document.createElement("div");
        mark.className = "video-label";
        mark.textContent = "▶ VIDEO";
        inner.append(mark);
      } else {
        element.alt = next.name;
        element.loading = "eager";
        element.decoding = "async";
      }
      inner.prepend(element);
      card.append(inner);

      // Listen *before* setting src so cached media cannot race past us.
      const pendingDimensions = waitForOriginalDimensions(element, isVideo);
      element.src = next.url;
      if (isVideo) element.load();
      const dimensions = await pendingDimensions;
      if (addRevision !== revision) return; // Restart while loading.
      if (!dimensions) {
        console.warn("Skipping media whose dimensions could not be loaded:", next.name);
        used.add(next.id);
        return;
      }

      // Photo-inner (and thus the white frame) follows the original photo/video.
      inner.style.aspectRatio = `${dimensions.width} / ${dimensions.height}`;
      stage.append(card);
      const coords = placeCard(card, cards.length);
      used.add(next.id);
      cards.push({element:card, coords, id:next.id});
      requestAnimationFrame(() => requestAnimationFrame(() => card.classList.add("visible")));
      setProgress();
      if (cards.length >= settings.capacity) scheduleReset();
    } catch (error) {
      console.warn("Unable to display media:", next.name, error);
      used.add(next.id);
    } finally {
      currentlyAdding = false;
    }
  }
  function scheduleReset() {
    if (resetting) return;
    resetting=true;
    const currentRevision=revision;
    setTimeout(()=>{if (revision===currentRevision) reset();},3300);
  }
  function reset() {
    revision++; resetting=false; used.clear();
    cards.forEach(x=>{x.element.classList.add("leaving");x.element.querySelector("video")?.pause();});
    const leftovers=cards;cards=[];setProgress();
    setTimeout(()=>leftovers.forEach(x=>x.element.remove()),900);
    if (!paused) setTimeout(()=>{if (!paused && !resetting) addOne();},1050);
  }
  function runTimer() { if (timer) clearInterval(timer);timer=setInterval(addOne,Math.max(1,settings.interval)*1000); }
  function pauseToggle() {paused=!paused;const btn=$("pause");if (btn) btn.textContent=paused?"▶ Resume":"Ⅱ Pause";if(!paused && !cards.length)addOne();}
  function fullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(()=>{});
    else document.exitFullscreen?.();
  }
  async function getSettings() {
    try {
      const cfg=await request("/api/config");const previous=JSON.stringify(settings);
      settings={...settings,...cfg};
      if (JSON.stringify(settings)!==previous) runTimer();
      if (!isDisplay && !initialized) {
        $("localFolder").value=cfg.local_folder || "";
        $("driveFolder").value=cfg.drive_folder || "";
        $("interval").value=cfg.interval;$("capacity").value=cfg.capacity;
        $("mixVideos").checked=cfg.mix_videos;$("shuffle").checked=cfg.shuffle;$("videoSound").checked=cfg.video_sound;
        updateOutputs();
      }
      initialized=true;setProgress();
    } catch(e){console.warn("Settings unavailable",e);}
  }
  async function getMedia() {
    try {
      const newItems=(await request("/api/media")).items;
      const known=new Set(media.map(m=>m.id));
      if(media.length)priority.push(...newItems.filter(m=>!known.has(m.id)).map(m=>m.id));
      media=newItems;
      if (!cards.length && !resetting && !paused) addOne();
      setProgress();
    } catch(e){notice(e.message);}
  }
  async function getStatus() {
    if(isDisplay)return;
    try {
      const s=await request("/api/status"),target=$("syncStatus");
      target.classList.toggle("good",!!s.last_sync&&!s.error);
      target.classList.toggle("error",!!s.error);
      let phrase;
      if(s.syncing)phrase="Syncing Google Drive…";
      else if(s.error)phrase=`Drive: ${s.error}`;
      else if(!s.drive_folder_set)phrase="Local folder active · Drive not linked";
      else if(!s.drive_connected)phrase="Drive folder saved · authorise Google to sync";
      else if(s.last_sync)phrase=`Drive synced · ${s.last_result?.downloaded||0} new files`;
      else phrase="Drive connected · waiting for first sync";
      target.querySelector("span:last-child").textContent=phrase;
    } catch(e){console.warn(e);}
  }
  async function save(key,value) {
    try {
      const cfg=await request("/api/config",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({[key]:value})});
      settings={...settings,...cfg};runTimer();notice("✓ Saved");getStatus();
    } catch(e){notice(`⚠ ${e.message}`);}
  }
  function updateOutputs() {
    if ($("intervalValue"))$("intervalValue").textContent=`${$("interval").value} seconds`;
    if ($("capacityValue"))$("capacityValue").textContent=`${$("capacity").value} items`;
  }
  function init() {
    $("reset")?.addEventListener("click",reset);
    $("pause")?.addEventListener("click",pauseToggle);
    $("fullscreen")?.addEventListener("click",fullscreen);
    $("soundButton")?.addEventListener("click",()=>{
      audioAllowed=!audioAllowed;
      settings.video_sound=audioAllowed;
      document.querySelectorAll(".photo-card video").forEach(v=>v.muted=!audioAllowed);
      $("soundButton").textContent=audioAllowed?"♫ Mute":"♫ Enable sound";
    });
    if (!isDisplay) {
      $("openDisplay").addEventListener("click",()=>window.open("/display","_blank"));
      $("saveFolder").addEventListener("click",()=>save("local_folder",$("localFolder").value));
      $("saveDrive").addEventListener("click",()=>save("drive_folder",$("driveFolder").value));
      $("syncNow").addEventListener("click",async()=>{
        $("syncNow").disabled=true;notice("Syncing…");
        try {await request("/api/sync",{method:"POST"});await getMedia();notice("✓ Sync complete");}
        catch(e){notice(`⚠ ${e.message}`);} finally{$("syncNow").disabled=false;getStatus();}
      });
      for(const key of ["interval","capacity"]) {
        $(key).addEventListener("input",updateOutputs);
        $(key).addEventListener("change",()=>save(key,Number($(key).value)));
      }
      for(const [id,key] of [["mixVideos","mix_videos"],["shuffle","shuffle"],["videoSound","video_sound"]])
        $(id).addEventListener("change",()=>save(key,$(id).checked));
    }
    document.addEventListener("keydown",(e)=>{
      if ((e.target.tagName==="INPUT"))return;
      if(e.key===" "){e.preventDefault();pauseToggle();}
      if(e.key.toLowerCase()==="r")reset();
      if(e.key.toLowerCase()==="f" && isDisplay)fullscreen();
    });
    // Auto-hide projector controls after mouse inactivity
    if (isDisplay) {
        const displayWrap = document.querySelector(".display-wrap");
        let hideToolbarTimer;

        function showToolbar() {
            displayWrap.classList.add("controls-visible");

            clearTimeout(hideToolbarTimer);

            hideToolbarTimer = setTimeout(() => {
                displayWrap.classList.remove("controls-visible");
            }, 2000);
        }

        document.addEventListener("pointermove", showToolbar);
        document.addEventListener("pointerdown", showToolbar);
        document.addEventListener("keydown", showToolbar);

        // Show controls briefly when opening the projector
        showToolbar();
    }
    Promise.all([getSettings(),getMedia()]).then(()=>{runTimer();getStatus();});
    setInterval(getMedia,6000);setInterval(getSettings,7000);setInterval(getStatus,12000);
  }
  init();
})();
