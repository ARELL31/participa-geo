<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer><Name>districts_2023</Name><UserStyle><Title>Distritos federales marco 2023</Title><FeatureTypeStyle><Rule>
    <PolygonSymbolizer><Fill><CssParameter name="fill">#f4dbe3</CssParameter><CssParameter name="fill-opacity">0.18</CssParameter></Fill><Stroke><CssParameter name="stroke">#801b43</CssParameter><CssParameter name="stroke-width">0.65</CssParameter></Stroke></PolygonSymbolizer>
  </Rule><Rule>
    <MaxScaleDenominator>8000000</MaxScaleDenominator>
    <TextSymbolizer>
      <Label><ogc:PropertyName>label</ogc:PropertyName></Label>
      <Font><CssParameter name="font-family">DejaVu Sans</CssParameter><CssParameter name="font-size">10</CssParameter><CssParameter name="font-style">normal</CssParameter><CssParameter name="font-weight">bold</CssParameter></Font>
      <LabelPlacement><PointPlacement><AnchorPoint><AnchorPointX>0.5</AnchorPointX><AnchorPointY>0.5</AnchorPointY></AnchorPoint></PointPlacement></LabelPlacement>
      <Halo><Radius>1.5</Radius><Fill><CssParameter name="fill">#ffffff</CssParameter></Fill></Halo>
      <Fill><CssParameter name="fill">#54152f</CssParameter></Fill>
    </TextSymbolizer>
  </Rule></FeatureTypeStyle></UserStyle></NamedLayer>
</StyledLayerDescriptor>
