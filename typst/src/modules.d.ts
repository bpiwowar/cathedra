declare module "virtual:docs" {
  const docs: Record<string, string>;
  export default docs;
}
declare module "course-widgets" {
  const widgets: Record<string, { component: unknown; steps?: (props: any) => number }>;
  export default widgets;
}
