#import "/slide-app/lib/slides.typ": *
#import "/slide-app/templates/academic/academic.typ": academic

#let course-data = (
  ref-links: json("/lib/refs-links.json"),
  image-cache: json("/.cache/images/manifest.json"),
  widget-shots: json("/.cache/widgets/manifest.json"),
)

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [A Demo Course],
  data: course-data,
)
