#import "/common/course.typ": *

#show: course-theme.with(config-info(
  title: [Demo deck],
  author: [A. Teacher],
  date: [Lecture 1],
))

#title-slide()

= First part

#include "/modules/intro/intro.typ"

=== A slide with steps

- One
#pause
- Two, with a #link("https://example.org")[link]

=== See the details

#details-link("more")[More on this]

#details("more", title: [In detail])[
  === Detailed slide

  Hidden in the appendix.
]
