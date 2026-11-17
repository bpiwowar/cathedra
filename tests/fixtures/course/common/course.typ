#import "/slide-app/lib/slides.typ": *
#import "/slide-app/templates/academic/academic.typ": academic

#let course-data = if generated {
  (
    ref-links: json("/lib/refs-links.json"),
    widget-shots: json("/.cache/widgets/manifest.json"),
  )
} else { (:) }

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [A Demo Course],
  data: course-data,
)
