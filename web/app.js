const calendarGrid = document.getElementById("calendarGrid");
const monthTitle = document.getElementById("monthTitle");
const subtitle = document.getElementById("subtitle");
const container = document.getElementById("courtContainer");
const progressBar = document.getElementById("progressBar");
const progressContainer = document.getElementById("progressContainer");

let currentMonth = new Date();
let selectedButton = null;
let monthCache = {};

document.getElementById("prevMonth").addEventListener("click", () => {
  currentMonth.setMonth(currentMonth.getMonth() - 1);
  renderCalendar();
});

document.getElementById("nextMonth").addEventListener("click", () => {
  currentMonth.setMonth(currentMonth.getMonth() + 1);
  renderCalendar();
});

function renderCalendar() {
  calendarGrid.innerHTML = "";
  container.innerHTML = "";
  monthCache = {};

  if (progressContainer) {
    progressContainer.classList.add("loading");
  }

  if (progressBar) {
    progressBar.style.width = "40%";
  }

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  monthTitle.textContent = currentMonth.toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  const firstDay = new Date(year, month, 1);
  const firstWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  subtitle.textContent = `Loading availability for ${monthTitle.textContent}...`;

  for (let i = 0; i < firstWeekday; i++) {
    const empty = document.createElement("button");
    empty.className = "calendar-day empty";
    empty.disabled = true;
    calendarGrid.appendChild(empty);
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const buttonsByDate = {};

  for (let day = 1; day <= daysInMonth; day++) {
    const dateObj = new Date(year, month, day);
    const date = formatDateForApi(year, month, day);

    const button = document.createElement("button");
    button.dataset.date = date;

    if (dateObj < today) {
      button.className = "calendar-day past";
      button.disabled = true;
      button.innerHTML = `
        <strong>${day}</strong>
        <span class="label">Past</span>
      `;
    } else {
      button.className = "calendar-day loading";
      button.innerHTML = `
        <strong>${day}</strong>
        <span class="label">Loading...</span>
      `;

      button.addEventListener("click", () => {
        const cachedData = monthCache[date];

        if (cachedData) {
          selectDay(button, cachedData);
        }
      });

      buttonsByDate[date] = button;
    }

    calendarGrid.appendChild(button);
  }

  loadMonthAvailability(year, month + 1, buttonsByDate);
}

async function loadMonthAvailability(year, month, buttonsByDate) {
  try {
    const response = await fetch(`/api/month?year=${year}&month=${month}`);

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const data = await response.json();
    const dates = data.dates || {};
    const dateEntries = Object.entries(dates);

    let completed = 0;
    const total = Object.keys(buttonsByDate).length || 1;

    for (const [date, availability] of dateEntries) {
      monthCache[date] = availability;

      const button = buttonsByDate[date];

      if (!button) {
        continue;
      }

      if (availability.error) {
        button.className = "calendar-day";
        button.querySelector(".label").textContent = "Error";
      } else {
        const hasAnyBookedTime = availability.courts.some(
          court => court.booked && court.booked.length > 0
        );

        button.className = `calendar-day ${hasAnyBookedTime ? "booked" : "open"}`;
        button.querySelector(".label").textContent = hasAnyBookedTime ? "Busy" : "Open";
      }

      completed++;
      updateProgress(completed, total);
    }

    subtitle.textContent = `Loaded ${monthTitle.textContent}. Click a day for details.`;
    autoSelectTodayIfVisible();
    if (progressContainer) {
        progressContainer.classList.remove("loading");
    }

    if (progressBar) {
        progressBar.style.width = "100%";
    }
  } catch (error) {
    console.error(error);
    subtitle.textContent = "Could not load monthly availability data.";
    if (progressContainer) {
        progressContainer.classList.remove("loading");
    }
  }
}

function autoSelectTodayIfVisible() {
  const today = new Date();
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  if (today.getFullYear() !== year || today.getMonth() !== month) {
    return;
  }

  const todayDate = formatDateForApi(year, month, today.getDate());
  const todayButton = document.querySelector(`[data-date="${todayDate}"]`);
  const todayData = monthCache[todayDate];

  if (todayButton && todayData) {
    selectDay(todayButton, todayData);
  }
}

function updateProgress(completed, total) {
  if (!progressBar) return;

  const percent = Math.round((completed / total) * 100);
  progressBar.style.width = `${percent}%`;
}

function selectDay(button, data) {
  if (selectedButton) {
    selectedButton.classList.remove("selected");
  }

  selectedButton = button;
  button.classList.add("selected");

  container.innerHTML = "<p class='empty'>Loading details...</p>";
  renderAvailability(data);
}

function formatDateForApi(year, monthIndex, day) {
  const month = String(monthIndex + 1).padStart(2, "0");
  const dateDay = String(day).padStart(2, "0");
  return `${month}/${dateDay}/${year}`;
}

function renderAvailability(data) {
  subtitle.textContent = `Date: ${data.date} • Last updated: ${formatDateTime(data.lastUpdated)}`;
  container.innerHTML = "";

  data.courts.forEach((court) => {
    const hasBookedSlots = court.booked && court.booked.length > 0;
    const statusText = getCourtStatusText(court);

    const card = document.createElement("article");
    card.className = "court-card";

    card.innerHTML = `
      <h2>${court.name}</h2>

      <div class="status ${hasBookedSlots ? "booked" : "open"}">
        ${statusText}
      </div>

      <div class="slot-section">
        <h3>Booked / Unavailable</h3>
        ${
          hasBookedSlots
            ? `<div class="slot-list">${court.booked.map(slot => `<span class="slot booked">${slot}</span>`).join("")}</div>`
            : `<p class="empty">No booked time found.</p>`
        }
      </div>

      <div class="slot-section">
        <h3>Available</h3>
        ${
          court.available && court.available.length
            ? `<div class="slot-list">${court.available.map(slot => `<span class="slot available">${slot}</span>`).join("")}</div>`
            : `<p class="empty">No available slots listed.</p>`
        }
      </div>
    `;

    container.appendChild(card);
  });
}

function formatDateTime(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function getCourtStatusText(court) {
  const booked = court.booked || [];

  if (booked.length === 0) {
    return "Open";
  }

  const hasLongBlock = booked.some(slot => {
    return slot.includes("8:00 am") || slot.includes("9:00 am") || slot.includes("10:00 am");
  });

  if (hasLongBlock) {
    return "Mostly / Fully Booked";
  }

  return "Partially Booked";
}

renderCalendar();