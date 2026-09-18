function updateThemePictures() {
    const body = document.body;
    const mediaAttr = body.getAttribute("data-md-color-media") || "";
    const isDark = mediaAttr.includes("dark");

    const pictures = document.querySelectorAll("picture");

    pictures.forEach((picture) => {
        const darkSrc = picture.getAttribute("data-dark");
        const lightSrc = picture.getAttribute("data-light");

        const source = picture.querySelector("source");
        const img = picture.querySelector("img");

        if (isDark) {
            source.media = "all";
            source.srcset = darkSrc;
            img.src = darkSrc;
        } else {
            source.media = "not all";
            source.srcset = lightSrc;
            img.src = lightSrc;
        }
    });
}

// Run on load
updateThemePictures();

// Watch for changes to the theme
const observer = new MutationObserver(updateThemePictures);
observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-media"],
});

document$.subscribe(() => {
    document.querySelectorAll(".headerlink").forEach((link) => {
        link.setAttribute("data-clipboard-text", link.href);
    });
});