--
-- PostgreSQL database dump
--

\restrict V8bwAB2HFF5X2Iq9fpk7x2IQijn93sKhOLoLClMWoKVj4LmuXxygtfMt7hd3Xj8

-- Dumped from database version 17.8 (Homebrew)
-- Dumped by pg_dump version 17.8 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_raster; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_raster WITH SCHEMA public;


--
-- Name: EXTENSION postgis_raster; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis_raster IS 'PostGIS raster types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: model_test_metrics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.model_test_metrics (
    created_at text,
    metrics_json text
);


ALTER TABLE public.model_test_metrics OWNER TO postgres;

--
-- Name: predicted_rasters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.predicted_rasters (
    rid integer NOT NULL,
    rast public.raster,
    filename text,
    CONSTRAINT enforce_height_rast CHECK ((public.st_height(rast) = 512)),
    CONSTRAINT enforce_nodata_values_rast CHECK ((public._raster_constraint_nodata_values(rast) = '{0.0000000000}'::numeric[])),
    CONSTRAINT enforce_num_bands_rast CHECK ((public.st_numbands(rast) = 1)),
    CONSTRAINT enforce_out_db_rast CHECK ((public._raster_constraint_out_db(rast) = '{f}'::boolean[])),
    CONSTRAINT enforce_pixel_types_rast CHECK ((public._raster_constraint_pixel_types(rast) = '{8BUI}'::text[])),
    CONSTRAINT enforce_scalex_rast CHECK ((round((public.st_scalex(rast))::numeric, 10) = round(0.00008983152841195215, 10))),
    CONSTRAINT enforce_scaley_rast CHECK ((round((public.st_scaley(rast))::numeric, 10) = round((- 0.00008983152841195215), 10))),
    CONSTRAINT enforce_srid_rast CHECK ((public.st_srid(rast) = 4326)),
    CONSTRAINT enforce_width_rast CHECK ((public.st_width(rast) = 512))
);


ALTER TABLE public.predicted_rasters OWNER TO postgres;

--
-- Name: predicted_rasters_rid_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.predicted_rasters_rid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.predicted_rasters_rid_seq OWNER TO postgres;

--
-- Name: predicted_rasters_rid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.predicted_rasters_rid_seq OWNED BY public.predicted_rasters.rid;


--
-- Name: spill_analysis_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.spill_analysis_results (
    filename text,
    source_image text,
    source_image_path text,
    predicted_mask_path text,
    area_px bigint,
    area_m2 double precision,
    coverage_pct double precision,
    centroid_x bigint,
    centroid_y bigint,
    perimeter_px double precision,
    perimeter_m double precision,
    orientation_deg double precision,
    spread_ratio double precision,
    num_components bigint,
    components_json text,
    compactness double precision,
    mean_intensity double precision,
    max_intensity double precision,
    std_intensity double precision,
    density_score double precision,
    contours_count bigint,
    spill_centroid_lon double precision,
    spill_centroid_lat double precision,
    distance_to_land_m bigint,
    distance_to_land_km double precision,
    land_proximity_class text,
    distance_to_coral_m bigint,
    distance_to_coral_km double precision,
    coral_proximity_class text,
    proximity_geom_type text,
    risk_score double precision,
    risk_level text,
    risk_factors text,
    date text,
    "time" text,
    crs text,
    width bigint,
    height bigint,
    pixel_size_x double precision,
    pixel_size_y double precision,
    bbox_left double precision,
    bbox_bottom double precision,
    bbox_right double precision,
    bbox_top double precision,
    center_lon double precision,
    center_lat double precision,
    upper_left_lon double precision,
    upper_left_lat double precision,
    upper_right_lon double precision,
    upper_right_lat double precision,
    lower_right_lon double precision,
    lower_right_lat double precision,
    lower_left_lon double precision,
    lower_left_lat double precision,
    analysis_created_at text,
    visual_report_path text,
    llm_report_html text,
    llm_report_path text
);


ALTER TABLE public.spill_analysis_results OWNER TO postgres;

--
-- Name: spill_info; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.spill_info (
    file text,
    source_path text,
    date text,
    "time" text,
    crs text,
    width bigint,
    height bigint,
    pixel_size_x double precision,
    pixel_size_y double precision,
    bbox_left double precision,
    bbox_bottom double precision,
    bbox_right double precision,
    bbox_top double precision,
    center_lon double precision,
    center_lat double precision,
    upper_left_lon double precision,
    upper_left_lat double precision,
    upper_right_lon double precision,
    upper_right_lat double precision,
    lower_right_lon double precision,
    lower_right_lat double precision,
    lower_left_lon double precision,
    lower_left_lat double precision,
    error text
);


ALTER TABLE public.spill_info OWNER TO postgres;

--
-- Name: predicted_rasters rid; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.predicted_rasters ALTER COLUMN rid SET DEFAULT nextval('public.predicted_rasters_rid_seq'::regclass);


--
-- Name: predicted_rasters enforce_max_extent_rast; Type: CHECK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE public.predicted_rasters
    ADD CONSTRAINT enforce_max_extent_rast CHECK ((public.st_envelope(rast) OPERATOR(public.@) '0103000020E61000000100000005000000A86297DF2CCD57C0D829B791755120C0A86297DF2CCD57C0CB2F1CE756B44E4045A6F380A0496040CB2F1CE756B44E4045A6F380A0496040D829B791755120C0A86297DF2CCD57C0D829B791755120C0'::public.geometry)) NOT VALID;


--
-- Name: predicted_rasters predicted_rasters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.predicted_rasters
    ADD CONSTRAINT predicted_rasters_pkey PRIMARY KEY (rid);


--
-- Name: predicted_rasters_st_convexhull_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx10; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx10 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx100; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx100 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1000; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1000 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1001; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1001 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1002; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1002 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1003; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1003 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1004; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1004 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1005; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1005 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1006; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1006 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1007; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1007 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1008; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1008 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1009; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1009 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx101; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx101 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1010; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1010 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1011; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1011 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1012; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1012 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1013; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1013 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1014; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1014 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1015; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1015 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1016; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1016 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1017; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1017 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1018; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1018 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1019; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1019 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx102; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx102 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1020; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1020 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1021; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1021 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1022; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1022 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1023; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1023 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1024; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1024 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1025; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1025 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1026; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1026 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1027; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1027 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1028; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1028 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1029; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1029 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx103; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx103 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1030; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1030 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1031; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1031 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1032; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1032 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1033; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1033 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1034; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1034 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1035; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1035 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1036; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1036 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1037; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1037 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1038; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1038 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1039; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1039 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx104; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx104 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1040; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1040 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1041; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1041 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1042; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1042 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1043; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1043 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1044; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1044 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1045; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1045 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1046; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1046 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1047; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1047 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1048; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1048 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1049; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1049 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx105; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx105 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1050; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1050 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1051; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1051 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1052; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1052 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1053; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1053 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1054; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1054 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1055; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1055 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1056; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1056 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1057; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1057 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1058; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1058 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1059; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1059 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx106; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx106 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1060; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1060 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1061; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1061 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1062; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1062 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1063; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1063 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1064; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1064 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1065; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1065 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1066; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1066 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1067; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1067 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1068; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1068 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1069; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1069 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx107; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx107 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1070; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1070 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1071; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1071 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1072; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1072 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1073; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1073 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1074; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1074 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1075; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1075 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1076; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1076 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1077; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1077 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1078; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1078 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1079; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1079 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx108; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx108 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1080; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1080 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1081; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1081 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1082; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1082 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1083; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1083 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1084; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1084 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1085; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1085 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1086; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1086 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1087; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1087 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1088; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1088 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1089; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1089 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx109; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx109 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1090; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1090 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1091; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1091 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1092; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1092 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1093; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1093 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1094; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1094 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1095; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1095 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1096; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1096 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1097; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1097 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1098; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1098 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1099; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1099 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx11; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx11 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx110; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx110 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1100; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1100 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1101; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1101 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1102; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1102 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1103; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1103 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1104; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1104 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1105; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1105 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1106; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1106 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1107; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1107 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1108; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1108 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1109; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1109 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx111; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx111 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1110; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1110 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1111; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1111 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1112; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1112 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1113; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1113 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1114; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1114 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1115; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1115 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1116; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1116 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1117; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1117 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1118; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1118 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1119; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1119 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx112; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx112 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1120; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1120 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1121; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1121 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1122; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1122 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1123; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1123 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1124; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1124 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1125; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1125 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1126; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1126 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1127; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1127 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1128; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1128 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1129; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1129 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx113; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx113 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1130; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1130 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1131; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1131 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1132; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1132 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1133; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1133 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1134; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1134 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1135; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1135 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1136; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1136 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1137; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1137 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1138; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1138 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1139; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1139 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx114; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx114 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1140; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1140 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1141; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1141 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1142; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1142 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1143; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1143 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1144; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1144 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1145; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1145 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1146; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1146 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1147; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1147 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1148; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1148 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1149; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1149 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx115; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx115 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1150; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1150 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1151; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1151 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1152; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1152 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1153; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1153 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1154; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1154 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1155; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1155 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1156; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1156 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1157; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1157 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1158; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1158 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1159; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1159 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx116; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx116 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1160; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1160 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1161; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1161 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1162; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1162 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1163; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1163 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1164; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1164 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1165; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1165 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1166; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1166 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1167; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1167 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1168; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1168 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1169; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1169 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx117; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx117 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1170; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1170 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1171; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1171 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1172; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1172 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1173; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1173 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1174; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1174 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1175; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1175 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1176; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1176 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1177; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1177 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1178; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1178 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1179; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1179 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx118; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx118 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1180; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1180 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1181; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1181 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1182; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1182 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1183; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1183 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1184; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1184 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1185; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1185 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1186; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1186 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1187; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1187 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1188; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1188 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1189; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1189 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx119; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx119 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1190; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1190 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1191; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1191 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1192; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1192 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1193; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1193 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1194; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1194 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1195; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1195 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1196; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1196 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1197; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1197 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1198; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1198 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx1199; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx1199 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx12; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx12 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx120; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx120 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx121; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx121 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx122; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx122 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx123; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx123 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx124; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx124 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx125; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx125 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx126; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx126 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx127; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx127 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx128; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx128 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx129; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx129 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx13; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx13 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx130; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx130 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx131; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx131 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx132; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx132 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx133; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx133 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx134; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx134 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx135; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx135 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx136; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx136 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx137; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx137 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx138; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx138 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx139; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx139 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx14; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx14 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx140; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx140 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx141; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx141 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx142; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx142 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx143; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx143 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx144; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx144 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx145; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx145 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx146; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx146 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx147; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx147 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx148; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx148 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx149; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx149 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx15; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx15 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx150; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx150 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx151; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx151 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx152; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx152 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx153; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx153 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx154; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx154 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx155; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx155 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx156; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx156 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx157; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx157 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx158; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx158 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx159; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx159 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx16; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx16 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx160; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx160 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx161; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx161 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx162; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx162 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx163; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx163 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx164; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx164 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx165; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx165 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx166; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx166 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx167; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx167 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx168; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx168 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx169; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx169 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx17; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx17 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx170; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx170 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx171; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx171 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx172; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx172 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx173; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx173 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx174; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx174 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx175; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx175 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx176; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx176 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx177; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx177 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx178; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx178 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx179; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx179 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx18; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx18 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx180; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx180 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx181; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx181 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx182; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx182 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx183; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx183 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx184; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx184 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx185; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx185 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx186; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx186 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx187; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx187 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx188; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx188 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx189; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx189 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx19; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx19 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx190; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx190 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx191; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx191 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx192; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx192 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx193; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx193 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx194; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx194 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx195; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx195 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx196; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx196 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx197; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx197 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx198; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx198 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx199; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx199 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx2 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx20; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx20 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx200; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx200 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx201; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx201 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx202; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx202 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx203; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx203 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx204; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx204 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx205; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx205 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx206; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx206 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx207; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx207 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx208; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx208 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx209; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx209 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx21; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx21 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx210; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx210 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx211; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx211 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx212; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx212 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx213; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx213 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx214; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx214 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx215; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx215 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx216; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx216 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx217; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx217 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx218; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx218 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx219; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx219 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx22; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx22 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx220; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx220 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx221; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx221 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx222; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx222 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx223; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx223 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx224; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx224 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx225; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx225 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx226; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx226 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx227; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx227 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx228; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx228 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx229; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx229 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx23; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx23 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx230; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx230 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx231; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx231 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx232; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx232 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx233; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx233 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx234; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx234 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx235; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx235 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx236; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx236 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx237; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx237 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx238; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx238 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx239; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx239 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx24; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx24 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx240; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx240 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx241; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx241 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx242; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx242 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx243; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx243 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx244; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx244 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx245; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx245 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx246; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx246 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx247; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx247 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx248; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx248 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx249; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx249 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx25; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx25 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx250; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx250 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx251; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx251 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx252; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx252 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx253; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx253 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx254; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx254 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx255; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx255 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx256; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx256 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx257; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx257 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx258; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx258 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx259; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx259 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx26; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx26 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx260; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx260 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx261; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx261 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx262; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx262 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx263; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx263 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx264; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx264 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx265; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx265 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx266; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx266 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx267; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx267 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx268; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx268 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx269; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx269 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx27; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx27 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx270; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx270 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx271; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx271 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx272; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx272 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx273; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx273 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx274; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx274 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx275; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx275 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx276; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx276 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx277; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx277 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx278; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx278 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx279; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx279 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx28; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx28 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx280; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx280 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx281; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx281 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx282; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx282 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx283; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx283 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx284; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx284 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx285; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx285 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx286; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx286 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx287; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx287 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx288; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx288 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx289; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx289 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx29; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx29 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx290; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx290 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx291; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx291 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx292; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx292 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx293; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx293 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx294; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx294 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx295; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx295 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx296; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx296 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx297; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx297 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx298; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx298 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx299; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx299 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx3 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx30; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx30 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx300; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx300 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx301; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx301 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx302; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx302 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx303; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx303 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx304; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx304 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx305; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx305 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx306; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx306 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx307; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx307 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx308; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx308 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx309; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx309 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx31; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx31 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx310; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx310 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx311; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx311 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx312; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx312 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx313; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx313 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx314; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx314 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx315; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx315 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx316; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx316 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx317; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx317 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx318; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx318 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx319; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx319 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx32; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx32 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx320; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx320 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx321; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx321 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx322; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx322 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx323; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx323 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx324; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx324 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx325; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx325 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx326; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx326 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx327; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx327 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx328; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx328 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx329; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx329 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx33; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx33 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx330; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx330 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx331; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx331 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx332; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx332 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx333; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx333 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx334; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx334 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx335; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx335 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx336; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx336 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx337; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx337 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx338; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx338 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx339; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx339 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx34; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx34 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx340; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx340 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx341; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx341 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx342; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx342 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx343; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx343 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx344; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx344 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx345; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx345 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx346; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx346 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx347; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx347 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx348; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx348 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx349; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx349 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx35; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx35 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx350; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx350 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx351; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx351 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx352; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx352 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx353; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx353 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx354; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx354 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx355; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx355 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx356; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx356 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx357; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx357 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx358; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx358 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx359; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx359 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx36; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx36 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx360; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx360 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx361; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx361 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx362; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx362 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx363; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx363 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx364; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx364 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx365; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx365 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx366; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx366 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx367; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx367 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx368; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx368 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx369; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx369 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx37; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx37 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx370; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx370 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx371; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx371 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx372; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx372 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx373; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx373 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx374; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx374 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx375; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx375 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx376; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx376 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx377; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx377 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx378; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx378 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx379; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx379 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx38; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx38 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx380; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx380 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx381; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx381 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx382; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx382 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx383; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx383 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx384; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx384 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx385; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx385 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx386; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx386 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx387; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx387 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx388; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx388 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx389; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx389 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx39; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx39 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx390; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx390 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx391; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx391 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx392; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx392 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx393; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx393 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx394; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx394 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx395; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx395 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx396; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx396 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx397; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx397 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx398; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx398 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx399; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx399 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx4 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx40; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx40 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx400; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx400 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx401; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx401 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx402; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx402 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx403; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx403 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx404; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx404 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx405; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx405 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx406; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx406 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx407; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx407 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx408; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx408 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx409; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx409 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx41; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx41 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx410; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx410 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx411; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx411 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx412; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx412 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx413; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx413 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx414; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx414 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx415; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx415 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx416; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx416 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx417; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx417 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx418; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx418 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx419; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx419 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx42; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx42 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx420; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx420 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx421; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx421 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx422; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx422 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx423; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx423 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx424; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx424 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx425; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx425 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx426; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx426 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx427; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx427 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx428; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx428 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx429; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx429 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx43; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx43 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx430; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx430 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx431; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx431 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx432; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx432 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx433; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx433 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx434; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx434 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx435; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx435 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx436; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx436 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx437; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx437 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx438; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx438 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx439; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx439 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx44; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx44 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx440; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx440 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx441; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx441 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx442; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx442 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx443; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx443 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx444; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx444 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx445; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx445 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx446; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx446 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx447; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx447 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx448; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx448 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx449; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx449 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx45; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx45 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx450; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx450 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx451; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx451 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx452; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx452 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx453; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx453 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx454; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx454 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx455; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx455 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx456; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx456 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx457; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx457 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx458; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx458 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx459; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx459 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx46; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx46 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx460; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx460 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx461; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx461 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx462; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx462 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx463; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx463 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx464; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx464 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx465; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx465 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx466; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx466 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx467; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx467 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx468; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx468 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx469; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx469 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx47; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx47 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx470; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx470 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx471; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx471 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx472; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx472 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx473; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx473 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx474; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx474 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx475; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx475 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx476; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx476 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx477; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx477 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx478; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx478 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx479; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx479 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx48; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx48 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx480; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx480 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx481; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx481 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx482; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx482 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx483; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx483 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx484; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx484 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx485; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx485 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx486; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx486 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx487; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx487 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx488; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx488 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx489; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx489 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx49; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx49 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx490; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx490 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx491; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx491 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx492; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx492 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx493; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx493 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx494; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx494 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx495; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx495 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx496; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx496 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx497; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx497 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx498; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx498 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx499; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx499 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx5; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx5 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx50; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx50 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx500; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx500 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx501; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx501 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx502; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx502 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx503; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx503 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx504; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx504 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx505; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx505 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx506; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx506 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx507; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx507 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx508; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx508 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx509; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx509 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx51; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx51 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx510; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx510 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx511; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx511 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx512; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx512 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx513; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx513 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx514; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx514 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx515; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx515 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx516; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx516 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx517; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx517 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx518; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx518 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx519; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx519 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx52; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx52 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx520; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx520 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx521; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx521 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx522; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx522 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx523; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx523 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx524; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx524 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx525; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx525 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx526; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx526 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx527; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx527 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx528; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx528 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx529; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx529 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx53; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx53 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx530; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx530 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx531; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx531 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx532; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx532 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx533; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx533 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx534; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx534 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx535; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx535 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx536; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx536 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx537; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx537 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx538; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx538 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx539; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx539 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx54; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx54 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx540; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx540 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx541; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx541 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx542; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx542 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx543; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx543 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx544; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx544 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx545; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx545 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx546; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx546 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx547; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx547 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx548; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx548 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx549; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx549 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx55; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx55 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx550; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx550 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx551; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx551 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx552; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx552 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx553; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx553 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx554; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx554 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx555; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx555 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx556; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx556 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx557; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx557 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx558; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx558 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx559; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx559 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx56; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx56 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx560; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx560 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx561; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx561 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx562; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx562 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx563; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx563 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx564; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx564 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx565; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx565 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx566; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx566 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx567; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx567 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx568; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx568 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx569; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx569 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx57; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx57 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx570; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx570 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx571; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx571 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx572; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx572 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx573; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx573 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx574; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx574 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx575; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx575 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx576; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx576 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx577; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx577 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx578; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx578 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx579; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx579 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx58; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx58 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx580; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx580 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx581; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx581 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx582; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx582 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx583; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx583 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx584; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx584 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx585; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx585 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx586; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx586 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx587; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx587 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx588; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx588 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx589; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx589 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx59; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx59 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx590; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx590 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx591; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx591 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx592; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx592 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx593; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx593 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx594; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx594 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx595; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx595 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx596; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx596 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx597; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx597 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx598; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx598 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx599; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx599 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx6 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx60; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx60 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx600; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx600 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx601; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx601 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx602; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx602 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx603; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx603 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx604; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx604 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx605; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx605 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx606; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx606 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx607; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx607 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx608; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx608 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx609; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx609 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx61; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx61 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx610; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx610 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx611; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx611 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx612; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx612 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx613; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx613 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx614; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx614 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx615; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx615 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx616; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx616 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx617; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx617 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx618; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx618 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx619; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx619 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx62; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx62 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx620; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx620 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx621; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx621 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx622; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx622 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx623; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx623 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx624; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx624 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx625; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx625 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx626; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx626 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx627; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx627 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx628; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx628 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx629; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx629 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx63; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx63 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx630; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx630 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx631; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx631 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx632; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx632 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx633; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx633 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx634; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx634 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx635; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx635 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx636; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx636 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx637; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx637 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx638; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx638 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx639; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx639 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx64; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx64 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx640; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx640 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx641; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx641 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx642; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx642 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx643; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx643 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx644; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx644 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx645; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx645 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx646; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx646 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx647; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx647 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx648; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx648 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx649; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx649 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx65; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx65 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx650; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx650 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx651; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx651 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx652; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx652 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx653; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx653 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx654; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx654 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx655; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx655 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx656; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx656 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx657; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx657 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx658; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx658 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx659; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx659 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx66; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx66 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx660; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx660 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx661; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx661 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx662; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx662 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx663; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx663 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx664; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx664 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx665; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx665 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx666; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx666 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx667; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx667 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx668; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx668 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx669; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx669 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx67; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx67 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx670; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx670 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx671; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx671 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx672; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx672 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx673; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx673 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx674; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx674 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx675; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx675 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx676; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx676 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx677; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx677 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx678; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx678 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx679; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx679 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx68; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx68 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx680; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx680 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx681; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx681 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx682; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx682 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx683; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx683 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx684; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx684 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx685; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx685 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx686; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx686 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx687; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx687 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx688; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx688 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx689; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx689 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx69; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx69 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx690; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx690 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx691; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx691 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx692; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx692 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx693; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx693 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx694; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx694 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx695; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx695 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx696; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx696 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx697; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx697 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx698; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx698 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx699; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx699 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx7 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx70; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx70 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx700; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx700 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx701; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx701 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx702; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx702 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx703; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx703 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx704; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx704 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx705; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx705 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx706; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx706 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx707; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx707 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx708; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx708 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx709; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx709 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx71; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx71 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx710; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx710 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx711; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx711 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx712; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx712 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx713; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx713 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx714; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx714 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx715; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx715 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx716; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx716 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx717; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx717 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx718; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx718 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx719; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx719 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx72; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx72 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx720; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx720 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx721; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx721 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx722; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx722 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx723; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx723 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx724; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx724 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx725; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx725 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx726; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx726 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx727; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx727 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx728; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx728 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx729; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx729 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx73; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx73 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx730; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx730 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx731; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx731 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx732; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx732 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx733; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx733 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx734; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx734 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx735; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx735 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx736; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx736 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx737; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx737 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx738; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx738 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx739; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx739 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx74; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx74 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx740; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx740 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx741; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx741 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx742; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx742 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx743; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx743 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx744; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx744 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx745; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx745 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx746; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx746 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx747; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx747 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx748; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx748 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx749; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx749 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx75; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx75 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx750; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx750 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx751; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx751 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx752; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx752 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx753; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx753 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx754; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx754 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx755; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx755 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx756; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx756 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx757; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx757 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx758; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx758 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx759; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx759 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx76; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx76 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx760; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx760 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx761; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx761 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx762; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx762 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx763; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx763 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx764; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx764 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx765; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx765 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx766; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx766 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx767; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx767 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx768; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx768 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx769; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx769 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx77; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx77 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx770; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx770 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx771; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx771 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx772; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx772 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx773; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx773 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx774; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx774 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx775; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx775 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx776; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx776 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx777; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx777 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx778; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx778 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx779; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx779 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx78; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx78 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx780; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx780 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx781; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx781 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx782; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx782 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx783; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx783 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx784; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx784 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx785; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx785 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx786; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx786 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx787; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx787 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx788; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx788 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx789; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx789 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx79; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx79 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx790; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx790 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx791; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx791 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx792; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx792 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx793; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx793 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx794; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx794 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx795; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx795 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx796; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx796 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx797; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx797 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx798; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx798 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx799; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx799 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx8; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx8 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx80; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx80 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx800; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx800 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx801; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx801 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx802; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx802 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx803; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx803 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx804; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx804 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx805; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx805 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx806; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx806 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx807; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx807 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx808; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx808 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx809; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx809 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx81; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx81 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx810; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx810 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx811; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx811 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx812; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx812 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx813; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx813 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx814; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx814 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx815; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx815 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx816; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx816 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx817; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx817 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx818; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx818 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx819; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx819 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx82; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx82 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx820; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx820 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx821; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx821 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx822; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx822 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx823; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx823 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx824; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx824 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx825; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx825 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx826; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx826 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx827; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx827 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx828; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx828 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx829; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx829 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx83; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx83 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx830; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx830 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx831; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx831 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx832; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx832 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx833; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx833 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx834; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx834 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx835; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx835 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx836; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx836 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx837; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx837 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx838; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx838 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx839; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx839 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx84; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx84 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx840; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx840 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx841; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx841 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx842; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx842 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx843; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx843 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx844; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx844 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx845; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx845 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx846; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx846 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx847; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx847 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx848; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx848 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx849; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx849 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx85; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx85 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx850; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx850 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx851; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx851 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx852; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx852 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx853; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx853 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx854; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx854 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx855; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx855 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx856; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx856 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx857; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx857 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx858; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx858 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx859; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx859 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx86; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx86 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx860; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx860 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx861; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx861 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx862; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx862 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx863; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx863 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx864; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx864 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx865; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx865 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx866; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx866 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx867; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx867 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx868; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx868 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx869; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx869 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx87; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx87 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx870; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx870 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx871; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx871 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx872; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx872 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx873; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx873 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx874; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx874 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx875; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx875 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx876; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx876 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx877; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx877 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx878; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx878 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx879; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx879 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx88; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx88 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx880; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx880 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx881; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx881 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx882; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx882 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx883; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx883 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx884; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx884 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx885; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx885 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx886; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx886 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx887; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx887 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx888; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx888 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx889; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx889 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx89; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx89 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx890; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx890 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx891; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx891 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx892; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx892 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx893; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx893 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx894; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx894 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx895; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx895 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx896; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx896 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx897; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx897 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx898; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx898 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx899; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx899 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx9 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx90; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx90 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx900; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx900 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx901; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx901 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx902; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx902 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx903; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx903 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx904; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx904 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx905; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx905 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx906; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx906 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx907; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx907 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx908; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx908 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx909; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx909 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx91; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx91 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx910; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx910 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx911; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx911 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx912; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx912 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx913; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx913 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx914; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx914 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx915; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx915 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx916; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx916 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx917; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx917 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx918; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx918 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx919; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx919 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx92; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx92 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx920; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx920 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx921; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx921 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx922; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx922 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx923; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx923 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx924; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx924 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx925; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx925 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx926; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx926 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx927; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx927 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx928; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx928 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx929; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx929 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx93; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx93 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx930; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx930 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx931; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx931 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx932; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx932 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx933; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx933 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx934; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx934 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx935; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx935 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx936; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx936 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx937; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx937 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx938; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx938 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx939; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx939 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx94; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx94 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx940; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx940 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx941; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx941 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx942; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx942 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx943; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx943 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx944; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx944 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx945; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx945 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx946; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx946 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx947; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx947 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx948; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx948 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx949; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx949 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx95; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx95 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx950; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx950 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx951; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx951 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx952; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx952 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx953; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx953 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx954; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx954 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx955; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx955 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx956; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx956 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx957; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx957 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx958; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx958 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx959; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx959 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx96; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx96 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx960; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx960 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx961; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx961 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx962; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx962 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx963; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx963 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx964; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx964 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx965; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx965 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx966; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx966 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx967; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx967 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx968; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx968 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx969; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx969 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx97; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx97 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx970; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx970 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx971; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx971 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx972; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx972 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx973; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx973 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx974; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx974 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx975; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx975 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx976; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx976 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx977; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx977 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx978; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx978 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx979; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx979 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx98; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx98 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx980; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx980 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx981; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx981 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx982; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx982 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx983; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx983 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx984; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx984 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx985; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx985 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx986; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx986 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx987; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx987 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx988; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx988 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx989; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx989 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx99; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx99 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx990; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx990 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx991; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx991 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx992; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx992 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx993; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx993 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx994; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx994 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx995; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx995 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx996; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx996 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx997; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx997 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx998; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx998 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- Name: predicted_rasters_st_convexhull_idx999; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX predicted_rasters_st_convexhull_idx999 ON public.predicted_rasters USING gist (public.st_convexhull(rast));


--
-- PostgreSQL database dump complete
--

\unrestrict V8bwAB2HFF5X2Iq9fpk7x2IQijn93sKhOLoLClMWoKVj4LmuXxygtfMt7hd3Xj8

