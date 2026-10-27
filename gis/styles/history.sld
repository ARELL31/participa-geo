<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xsi:schemaLocation="http://www.opengis.net/sld StyledLayerDescriptor.xsd"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>history</Name>
    <UserStyle>
      <Title>Historia de participación (información insuficiente en gris)</Title>
      <Abstract>Polígonos municipales; los territorios con información insuficiente se muestran en gris.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Name>insufficient</Name>
          <Title>Información insuficiente</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>eligible</ogc:PropertyName>
              <ogc:Literal>false</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#BDBDBD</CssParameter>
              <CssParameter name="fill-opacity">0.9</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#9E9E9E</CssParameter>
              <CssParameter name="stroke-width">0.4</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Name>data</Name>
          <Title>Participación</Title>
          <ElseFilter/>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#6F1739</CssParameter>
              <CssParameter name="fill-opacity">0.7</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#FFFFFF</CssParameter>
              <CssParameter name="stroke-width">0.4</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
