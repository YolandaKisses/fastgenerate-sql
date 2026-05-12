export type DemandField = {
  id: string;
  name: string;
  type: string;
  original_comment: string;
  supplementary_comment: string;
};

export type DemandDraftTable = {
  id: string;
  name: string;
  comment: string;
  relatedTables: string[];
  relatedTableDetails: Record<string, string>;
  savedPath?: string;
  fields: DemandField[];
};

export type DemandCategoryNode = {
  label: string;
  key: string;
  disabled?: boolean;
  children?: DemandCategoryNode[];
};

export type SchemaTableOption = {
  name: string;
  original_comment?: string;
};

export type DemandCategoryTreeResponse = {
  tree: DemandCategoryNode;
  root_key: string;
  root_label: string;
  default_key: string | null;
};
