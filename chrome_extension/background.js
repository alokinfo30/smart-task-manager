// Opens the Smart Task Manager production URL in a new tab when the extension icon is clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.create({ url: "https://staskma.streamlit.app/" });
});